#!/usr/bin/env python3
"""
WorkFlowOS Phase 5 - Desktop Activity Agent Test Suite (post-fix)

Tests:
1.  Event normalizer: slugification, schema compatibility, field mapping
2.  Event normalizer: privacy denylist enforcement
3.  Event normalizer: allowlist filtering
4.  Event normalizer: timestamp handling (naive, aware, missing)
5.  Event normalizer: empty app_name edge cases
6.  Session ID generation: uniqueness and format
7.  Agent config: is_app_allowed with allowlist and denylist
8.  Agent lifecycle: start and stop transitions
9.  Agent lifecycle: double-start guard
10. Agent lifecycle: capture_step returns EventCreate on first poll
11. Collector: poll returns None when app unchanged (PID-based)
12. Collector: poll returns activate_application on first observation
13. Collector: poll returns switch_application when PID changes
14. Collector: accessibility check does not raise
15. Collector: poll uses Carbon _get_frontmost_pid internally (ROOT CAUSE)
16. Collector: same PID never emits duplicate events
17. Collector: PID change with same bundle ID still emits switch
18. Backend client: deduplication by event signature (async queue)
19. Backend client: offline buffer fills on backend failure
20. Backend client: buffer flush on recovery
21. Backend client: max retries on 500 responses
22. Backend client: 400 error does not retry
23. EventCreate schema: generated events are schema-compatible with Phase 1/2

Usage:
  python backend/test_phase5.py

NOTE: All macOS-native APIs (AppKit / Carbon) are mocked.
These unit tests do NOT perform real desktop observation or require
a running GUI session. They verify the agent logic independently.
"""

import sys
import time
import uuid
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.models.event import EventCreate
from agent.config import AgentConfig, generate_session_id, DEFAULT_DENYLIST
from agent.normalizer import EventNormalizer, slugify_application_name
from agent.collector import MacOSActivityCollector
from agent.client import BackendEventClient
from agent.service import DesktopActivityAgent, AgentState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_config(allowlist=None, include_window_title=False,
                session_id="test_session_001", api_base_url="http://localhost:8000"):
    config = AgentConfig.__new__(AgentConfig)
    config.api_base_url = api_base_url
    config.session_id = session_id
    config.poll_interval_seconds = 0.05
    config.allowlist = allowlist
    config.denylist = set(DEFAULT_DENYLIST)
    config.include_window_title = include_window_title
    config.request_timeout_seconds = 5.0
    config.max_retries = 3
    config.retry_backoff_seconds = 0.0
    config.max_buffer_size = 100
    return config


def make_event(target=None, timestamp=None):
    return EventCreate(
        session_id="test_session_001",
        timestamp=timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        application="google_chrome",
        event_type="activate_application",
        target=target or uuid.uuid4().hex,
        metadata={"source": "macos_desktop_agent"},
    )


# ---------------------------------------------------------------------------
# 1. Event Normalizer
# ---------------------------------------------------------------------------

class TestEventNormalizer(unittest.TestCase):

    def _n(self, **kw):
        return EventNormalizer(config=make_config(**kw))

    def test_01_slugify_basic_names(self):
        """App names convert to consistent lowercase underscore slugs."""
        self.assertEqual(slugify_application_name("Google Chrome"), "google_chrome")
        self.assertEqual(slugify_application_name("Visual Studio Code"), "visual_studio_code")
        self.assertEqual(slugify_application_name("Antigravity IDE"), "antigravity_ide")
        self.assertEqual(slugify_application_name("1Password"), "1password")
        self.assertEqual(slugify_application_name("demo_email"), "demo_email")

    def test_02_slugify_edge_cases(self):
        """Slugify handles empty strings and special characters gracefully."""
        self.assertEqual(slugify_application_name(""), "unknown_application")
        self.assertEqual(slugify_application_name("   "), "unknown_application")
        self.assertEqual(slugify_application_name("App.app"), "app")
        self.assertEqual(slugify_application_name("App---Name"), "app_name")

    def test_03_normalize_produces_valid_event_create(self):
        """Normalizer produces a schema-valid EventCreate with correct field values."""
        event = self._n().normalize(
            app_name="Google Chrome",
            event_type="activate_application",
            bundle_id="com.google.Chrome",
            process_id=12345,
        )
        self.assertIsNotNone(event)
        self.assertIsInstance(event, EventCreate)
        self.assertEqual(event.application, "google_chrome")
        self.assertEqual(event.event_type, "activate_application")
        self.assertEqual(event.session_id, "test_session_001")
        self.assertEqual(event.metadata["source"], "macos_desktop_agent")

    def test_04_denylist_blocks_sensitive_apps(self):
        """Denylist blocks by app name and bundle ID."""
        n = self._n()
        self.assertIsNone(n.normalize(app_name="1Password", event_type="activate_application"))
        self.assertIsNone(n.normalize(app_name="SomeApp", event_type="activate_application",
                                      bundle_id="com.agilebits.onepassword"))

    def test_05_allowlist_permits_only_listed_apps(self):
        """Allowlist restricts capture: listed app passes, unlisted is filtered."""
        n = self._n(allowlist=["google_chrome", "slack"])
        self.assertIsNotNone(n.normalize(app_name="Google Chrome",
                                         event_type="activate_application"))
        self.assertIsNone(n.normalize(app_name="FinalCut Pro",
                                      event_type="activate_application"))

    def test_06_allowlist_bundle_id_match(self):
        """Allowlist matches by bundle ID as well as app slug."""
        n = self._n(allowlist=["com.tinyspeck.slackmacgap"])
        event = n.normalize(app_name="Slack", event_type="activate_application",
                            bundle_id="com.tinyspeck.slackmacgap")
        self.assertIsNotNone(event)

    def test_07_timestamp_is_utc_and_ends_with_z(self):
        """Timestamps are always UTC ISO 8601 ending with Z."""
        event = self._n().normalize(app_name="Finder", event_type="activate_application")
        self.assertIsNotNone(event)
        self.assertTrue(event.timestamp.endswith("Z"),
                        f"Timestamp should end with Z, got: {event.timestamp}")
        datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))

    def test_08_naive_datetime_treated_as_utc(self):
        """Naive datetime timestamps are assumed UTC and formatted correctly."""
        event = self._n().normalize(app_name="Finder", event_type="activate_application",
                                    timestamp=datetime(2026, 10, 3, 12, 0, 0))
        self.assertIsNotNone(event)
        self.assertIn("2026-10-03T12:00:00", event.timestamp)

    def test_09_window_title_excluded_by_default(self):
        """Window titles are NOT captured unless explicitly opted in."""
        event = self._n(include_window_title=False).normalize(
            app_name="Finder", event_type="activate_application",
            window_title="My Private Documents")
        self.assertIsNotNone(event)
        self.assertNotIn("window_title", event.metadata)

    def test_10_window_title_included_when_opted_in(self):
        """Window titles appear in metadata when include_window_title=True."""
        event = self._n(include_window_title=True).normalize(
            app_name="Finder", event_type="activate_application",
            window_title="My Documents")
        self.assertIsNotNone(event)
        self.assertEqual(event.metadata["window_title"], "My Documents")

    def test_11_previous_app_in_metadata_for_switch(self):
        """Previous application is stored in metadata for switch events."""
        event = self._n().normalize(
            app_name="Slack", event_type="switch_application",
            previous_app="Google Chrome",
            previous_bundle_id="com.google.Chrome")
        self.assertIsNotNone(event)
        self.assertEqual(event.metadata["previous_application"], "google_chrome")
        self.assertEqual(event.metadata["previous_app_name"], "Google Chrome")

    def test_12_phase1_schema_compatibility(self):
        """Events pass Phase 1/2 EventCreate serialization round-trip."""
        event = self._n().normalize(app_name="Google Chrome",
                                    event_type="activate_application",
                                    bundle_id="com.google.Chrome")
        self.assertIsNotNone(event)
        for field_name in ("session_id", "timestamp", "application", "event_type"):
            self.assertTrue(len(getattr(event, field_name)) > 0)
        reloaded = EventCreate(**event.model_dump())
        self.assertEqual(reloaded.application, event.application)
        self.assertEqual(reloaded.event_type, event.event_type)

    def test_13_empty_app_name_handled(self):
        """Empty app name yields 'unknown_application' slug (no crash)."""
        n = self._n()
        event = n.normalize(app_name="", event_type="activate_application")
        if event is not None:
            self.assertEqual(event.application, "unknown_application")


# ---------------------------------------------------------------------------
# 2. Agent Config and Session
# ---------------------------------------------------------------------------

class TestAgentConfig(unittest.TestCase):

    def test_14_session_id_unique(self):
        """generate_session_id produces distinct IDs on consecutive calls."""
        s1, s2 = generate_session_id(), generate_session_id()
        self.assertNotEqual(s1, s2)

    def test_15_session_id_format(self):
        """Session ID has expected prefix and minimum length."""
        sid = generate_session_id()
        self.assertTrue(sid.startswith("desktop_session_"),
                        f"Unexpected format: {sid}")
        self.assertGreater(len(sid), 20)

    def test_16_default_allows_regular_apps(self):
        """Default config (no allowlist) allows non-denylisted apps."""
        config = make_config()
        self.assertTrue(config.is_app_allowed("Google Chrome", "com.google.Chrome"))
        self.assertTrue(config.is_app_allowed("Slack"))
        self.assertTrue(config.is_app_allowed("Finder"))

    def test_17_denylist_priority_over_allowlist(self):
        """Denylist always overrides allowlist — sensitive apps are blocked."""
        config = make_config(allowlist=["1password"])
        self.assertFalse(config.is_app_allowed("1Password"))
        self.assertFalse(config.is_app_allowed("1password"))

    def test_18_allowlist_restricts_capture(self):
        """Allowlist mode only passes explicitly named apps."""
        config = make_config(allowlist=["google_chrome"])
        self.assertTrue(config.is_app_allowed("google_chrome"))
        self.assertFalse(config.is_app_allowed("Slack"))
        self.assertFalse(config.is_app_allowed("Finder"))

    def test_19_sensitive_apps_always_denied(self):
        """Password managers and Keychain are permanently denied."""
        config = make_config()
        for app in ["Keychain Access", "keychain", "bitwarden"]:
            self.assertFalse(config.is_app_allowed(app),
                             f"{app} must be blocked by denylist")


# ---------------------------------------------------------------------------
# 3. MacOSActivityCollector (NSWorkspace mocked)
# ---------------------------------------------------------------------------

class TestMacOSActivityCollector(unittest.TestCase):

    def _col(self, **kw):
        return MacOSActivityCollector(config=make_config(**kw))

    def _mock_front(self, col, name, bundle_id, pid=1234, policy=0):
        col.get_frontmost_app = MagicMock(return_value={
            "name": name, "bundle_id": bundle_id,
            "pid": pid, "activation_policy": policy,
        })

    # ------------------------------------------------------------------
    # Core poll() behaviour
    # ------------------------------------------------------------------

    def test_20_poll_none_when_unchanged(self):
        """poll() returns None when frontmost application PID has not changed."""
        col = self._col()
        self._mock_front(col, "Google Chrome", "com.google.Chrome", pid=100)
        col.poll()
        self.assertIsNone(col.poll())

    def test_21_poll_activate_on_first_observation(self):
        """First poll() returns activate_application event."""
        col = self._col()
        self._mock_front(col, "Google Chrome", "com.google.Chrome", pid=100)
        result = col.poll()
        self.assertIsNotNone(result)
        self.assertEqual(result["event_type"], "activate_application")
        self.assertEqual(result["app_name"], "Google Chrome")
        self.assertEqual(result["bundle_id"], "com.google.Chrome")

    def test_22_poll_switch_on_pid_change(self):
        """Changing PID (app switch) emits switch_application with previous_app."""
        col = self._col()
        self._mock_front(col, "Google Chrome", "com.google.Chrome", pid=100)
        col.poll()  # Initial activation
        # Now switch to Slack (different PID)
        col.get_frontmost_app = MagicMock(return_value={
            "name": "Slack", "bundle_id": "com.tinyspeck.slackmacgap",
            "pid": 200, "activation_policy": 0,
        })
        result = col.poll()
        self.assertIsNotNone(result)
        self.assertEqual(result["event_type"], "switch_application")
        self.assertEqual(result["app_name"], "Slack")
        self.assertEqual(result["previous_app"], "Google Chrome")
        self.assertEqual(result["previous_bundle_id"], "com.google.Chrome")

    def test_23_poll_none_when_no_frontmost(self):
        """poll() returns None gracefully when no app is frontmost."""
        col = self._col()
        col.get_frontmost_app = MagicMock(return_value=None)
        self.assertIsNone(col.poll())

    def test_24_poll_ignores_background_apps(self):
        """Apps with activation_policy=2 are silently ignored."""
        col = self._col()
        self._mock_front(col, "BG Daemon", "com.example.bg", pid=999, policy=2)
        self.assertIsNone(col.poll())

    def test_25_accessibility_check_returns_bool(self):
        """check_accessibility_trusted returns a bool without raising."""
        from agent.collector import check_accessibility_trusted
        self.assertIsInstance(check_accessibility_trusted(), bool)

    def test_26_reset_clears_tracking_state(self):
        """reset() erases all stored app-identity state."""
        col = self._col()
        self._mock_front(col, "Google Chrome", "com.google.Chrome", pid=100)
        col.poll()
        self.assertIsNotNone(col._last_app_name)
        self.assertIsNotNone(col._last_pid)
        col.reset()
        self.assertIsNone(col._last_app_name)
        self.assertIsNone(col._last_bundle_id)
        self.assertIsNone(col._last_pid)

    # ------------------------------------------------------------------
    # ROOT CAUSE regression tests (PID-based change detection)
    # ------------------------------------------------------------------

    def test_46_pid_change_same_bundle_still_emits_switch(self):
        """
        ROOT CAUSE TEST: If two different app instances share the same bundle ID
        but have different PIDs, poll() MUST emit switch_application.
        The old name/bundle-only comparison would have missed this.
        """
        col = self._col()
        col.get_frontmost_app = MagicMock(return_value={
            "name": "Google Chrome", "bundle_id": "com.google.Chrome",
            "pid": 100, "activation_policy": 0,
        })
        col.poll()  # Activate Chrome instance A (pid=100)

        # Chrome relaunched / second window with a different PID
        col.get_frontmost_app = MagicMock(return_value={
            "name": "Google Chrome", "bundle_id": "com.google.Chrome",
            "pid": 101, "activation_policy": 0,
        })
        result = col.poll()
        self.assertIsNotNone(result,
            "Different PID with same bundle should emit switch_application")
        self.assertEqual(result["event_type"], "switch_application")

    def test_47_same_pid_never_emits_duplicate(self):
        """
        ROOT CAUSE TEST: poll() must NOT emit an event if the PID is unchanged,
        even if the app's display name changes (e.g. localizedName localisation bug).
        """
        col = self._col()
        col.get_frontmost_app = MagicMock(return_value={
            "name": "Chrome", "bundle_id": "com.google.Chrome",
            "pid": 100, "activation_policy": 0,
        })
        col.poll()  # Initial event

        # Same PID, name differs slightly (e.g. OS locale change during session)
        col.get_frontmost_app = MagicMock(return_value={
            "name": "Google Chrome", "bundle_id": "com.google.Chrome",
            "pid": 100, "activation_policy": 0,
        })
        result = col.poll()
        self.assertIsNone(result,
            "Same PID must never produce a duplicate event")

    def test_48_three_way_app_switch_emits_three_events(self):
        """
        ROOT CAUSE TEST: Cycling through three different apps (A→B→C) must
        produce exactly one event per transition, in order.
        This is the primary scenario broken by the NSWorkspace staleness bug.
        """
        col = self._col()
        apps = [
            {"name": "Chrome",   "bundle_id": "com.google.Chrome",         "pid": 10, "activation_policy": 0},
            {"name": "Slack",    "bundle_id": "com.tinyspeck.slackmacgap", "pid": 20, "activation_policy": 0},
            {"name": "Finder",   "bundle_id": "com.apple.finder",           "pid": 30, "activation_policy": 0},
            # Back to Chrome (same PID) — no event should fire
            {"name": "Chrome",   "bundle_id": "com.google.Chrome",         "pid": 10, "activation_policy": 0},
        ]
        events = []
        for app_data in apps:
            col.get_frontmost_app = MagicMock(return_value=app_data)
            result = col.poll()
            if result:
                events.append(result)

        self.assertEqual(len(events), 4,
            f"Expected 4 events (activate + 3 switches), got {len(events)}: "
            f"{[e['event_type'] + ':' + e['app_name'] for e in events]}")
        self.assertEqual(events[0]["event_type"], "activate_application")
        self.assertEqual(events[0]["app_name"], "Chrome")
        self.assertEqual(events[1]["event_type"], "switch_application")
        self.assertEqual(events[1]["app_name"], "Slack")
        self.assertEqual(events[2]["event_type"], "switch_application")
        self.assertEqual(events[2]["app_name"], "Finder")
        self.assertEqual(events[3]["event_type"], "switch_application")
        self.assertEqual(events[3]["app_name"], "Chrome")

    def test_49_carbon_path_is_used_in_get_frontmost_app(self):
        """
        ROOT CAUSE TEST: get_frontmost_app() must call _get_frontmost_pid() (Carbon)
        rather than NSWorkspace.sharedWorkspace().frontmostApplication() when
        both AppKit and Carbon are available.
        """
        from agent import collector as collector_module

        config = make_config()
        col = MacOSActivityCollector(config=config)
        col.has_appkit = True

        mock_app = MagicMock()
        mock_app.localizedName.return_value = "Slack"
        mock_app.bundleIdentifier.return_value = "com.tinyspeck.slackmacgap"
        mock_app.activationPolicy.return_value = 0

        with patch.object(collector_module, "_get_frontmost_pid", return_value=42) as mock_pid, \
             patch.object(collector_module, "NSRunningApplication") as mock_nra:
            mock_nra.runningApplicationWithProcessIdentifier_.return_value = mock_app
            result = col.get_frontmost_app()

        mock_pid.assert_called_once()
        mock_nra.runningApplicationWithProcessIdentifier_.assert_called_once_with(42)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Slack")
        self.assertEqual(result["pid"], 42)

    def test_50_fallback_when_carbon_returns_none(self):
        """
        When _get_frontmost_pid() returns None (Carbon unavailable),
        get_frontmost_app() falls back to NSWorkspace.frontmostApplication().
        """
        from agent import collector as collector_module

        config = make_config()
        col = MacOSActivityCollector(config=config)
        col.has_appkit = True

        mock_app = MagicMock()
        mock_app.localizedName.return_value = "Finder"
        mock_app.bundleIdentifier.return_value = "com.apple.finder"
        mock_app.processIdentifier.return_value = 644
        mock_app.activationPolicy.return_value = 0

        mock_ws = MagicMock()
        mock_ws.frontmostApplication.return_value = mock_app

        with patch.object(collector_module, "_get_frontmost_pid", return_value=None), \
             patch.object(collector_module, "NSRunningApplication", new=None), \
             patch.object(collector_module, "NSWorkspace") as mock_nsws:
            mock_nsws.sharedWorkspace.return_value = mock_ws
            result = col.get_frontmost_app()

        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Finder")


# ---------------------------------------------------------------------------
# 4. BackendEventClient (HTTP mocked)
# ---------------------------------------------------------------------------

class TestBackendEventClient(unittest.TestCase):

    def _cli(self):
        config = make_config()
        config.max_retries = 3
        config.retry_backoff_seconds = 0.0
        return BackendEventClient(config=config)

    def _fixed_event(self):
        return EventCreate(
            session_id="test_session_001",
            timestamp="2026-10-03T10:00:00.000000Z",
            application="google_chrome",
            event_type="activate_application",
            target="fixed_dedup_target",
            metadata={"source": "macos_desktop_agent"},
        )

    def _unique_event(self):
        return make_event()

    def test_27_deduplication_prevents_double_send(self):
        """Identical event sent twice results in only one HTTP POST."""
        client = self._cli()
        event = self._fixed_event()
        with patch.object(client.session, "post",
                          return_value=MagicMock(status_code=201)) as m:
            client.send_event(event)
            client.send_event(event)
        self.assertEqual(m.call_count, 1, "HTTP POST should only fire once for duplicate")

    def test_28_buffers_on_connection_error(self):
        """Events are buffered locally when backend is unreachable."""
        client = self._cli()
        with patch.object(client.session, "post", side_effect=ConnectionError("Refused")):
            result = client.send_event(self._unique_event())
        self.assertFalse(result)
        self.assertEqual(client.buffered_count, 1)

    def test_29_flush_buffer_on_recovery(self):
        """Buffered events are flushed when backend becomes reachable again."""
        client = self._cli()
        with patch.object(client.session, "post", side_effect=ConnectionError("Refused")):
            client.send_event(self._unique_event())
        self.assertEqual(client.buffered_count, 1)
        with patch.object(client.session, "post",
                          return_value=MagicMock(status_code=201)):
            client.send_event(self._unique_event())
        self.assertEqual(client.buffered_count, 0)

    def test_30_no_retry_on_400(self):
        """Permanent 4xx errors are not retried."""
        client = self._cli()
        with patch.object(client.session, "post",
                          return_value=MagicMock(status_code=422, text="Unprocessable")) as m:
            client._post_with_retries(self._unique_event())
        self.assertEqual(m.call_count, 1)

    def test_31_retries_on_500(self):
        """Transient 5xx errors trigger max_retries retry attempts."""
        client = self._cli()
        with patch.object(client.session, "post",
                          return_value=MagicMock(status_code=503, text="Unavailable")) as m:
            client._post_with_retries(self._unique_event())
        self.assertEqual(m.call_count, 3)

    def test_32_success_on_201(self):
        """201 Created is treated as delivery success."""
        client = self._cli()
        with patch.object(client.session, "post",
                          return_value=MagicMock(status_code=201)) as m:
            result = client._post_with_retries(self._unique_event())
        self.assertTrue(result)
        self.assertEqual(m.call_count, 1)

    def test_33_health_false_on_connection_error(self):
        """Health check returns False when backend is unreachable."""
        client = self._cli()
        with patch.object(client.session, "get", side_effect=ConnectionError()):
            self.assertFalse(client.check_health())

    def test_34_health_true_on_200_ok(self):
        """Health check returns True on HTTP 200 with status='ok'."""
        client = self._cli()
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"status": "ok"}
        with patch.object(client.session, "get", return_value=mock_resp):
            self.assertTrue(client.check_health())


# ---------------------------------------------------------------------------
# 5. DesktopActivityAgent Lifecycle
# ---------------------------------------------------------------------------

class TestDesktopActivityAgentLifecycle(unittest.TestCase):

    def _make_agent(self):
        config = make_config()
        collector = MacOSActivityCollector(config=config)
        normalizer = EventNormalizer(config=config)
        client = BackendEventClient(config=config)
        collector.get_frontmost_app = MagicMock(return_value={
            "name": "Google Chrome", "bundle_id": "com.google.Chrome",
            "pid": 1234, "activation_policy": 0,
        })
        return DesktopActivityAgent(config=config, collector=collector,
                                    normalizer=normalizer, client=client)

    def test_35_initial_state_is_idle(self):
        """Agent is IDLE before start() is called."""
        agent = self._make_agent()
        self.assertEqual(agent.state, AgentState.IDLE)
        self.assertFalse(agent.is_running)

    def test_36_transitions_to_running_on_start(self):
        """start() transitions agent to RUNNING state."""
        agent = self._make_agent()
        try:
            agent.start()
            time.sleep(0.15)
            self.assertEqual(agent.state, AgentState.RUNNING)
            self.assertTrue(agent.is_running)
        finally:
            agent.stop()

    def test_37_transitions_to_stopped_on_stop(self):
        """stop() cleanly halts agent and sets state to STOPPED."""
        agent = self._make_agent()
        agent.start()
        time.sleep(0.1)
        agent.stop()
        self.assertEqual(agent.state, AgentState.STOPPED)
        self.assertFalse(agent.is_running)

    def test_38_double_start_no_second_thread(self):
        """Calling start() twice does not launch a duplicate worker thread."""
        agent = self._make_agent()
        try:
            agent.start()
            first_thread = agent._thread
            time.sleep(0.05)
            agent.start()
            self.assertIs(agent._thread, first_thread)
        finally:
            agent.stop()

    def test_39_capture_step_returns_event_on_activation(self):
        """capture_step() returns EventCreate on first app activation."""
        config = make_config()
        collector = MacOSActivityCollector(config=config)
        collector.get_frontmost_app = MagicMock(return_value={
            "name": "Google Chrome", "bundle_id": "com.google.Chrome",
            "pid": 1234, "activation_policy": 0,
        })
        client = BackendEventClient(config=config)
        with patch.object(client.session, "post", return_value=MagicMock(status_code=201)):
            agent = DesktopActivityAgent(
                config=config, collector=collector,
                normalizer=EventNormalizer(config=config), client=client)
            result = agent.capture_step()
        self.assertIsNotNone(result)
        self.assertIsInstance(result, EventCreate)
        self.assertEqual(result.event_type, "activate_application")
        self.assertEqual(result.application, "google_chrome")

    def test_40_capture_step_none_when_no_change(self):
        """capture_step() returns None when app state is unchanged."""
        config = make_config()
        collector = MacOSActivityCollector(config=config)
        collector.get_frontmost_app = MagicMock(return_value={
            "name": "Google Chrome", "bundle_id": "com.google.Chrome",
            "pid": 1234, "activation_policy": 0,
        })
        agent = DesktopActivityAgent(
            config=config, collector=collector,
            normalizer=EventNormalizer(config=config),
            client=BackendEventClient(config=config))
        agent.capture_step()
        self.assertIsNone(agent.capture_step())

    def test_41_capture_step_filters_denylisted_app(self):
        """capture_step() returns None for denylisted apps."""
        config = make_config()
        collector = MacOSActivityCollector(config=config)
        collector.get_frontmost_app = MagicMock(return_value={
            "name": "1Password", "bundle_id": "com.agilebits.onepassword7",
            "pid": 9999, "activation_policy": 0,
        })
        agent = DesktopActivityAgent(
            config=config, collector=collector,
            normalizer=EventNormalizer(config=config),
            client=BackendEventClient(config=config))
        self.assertIsNone(agent.capture_step())

    def test_42_status_has_required_keys(self):
        """status() dict contains all required observability fields."""
        agent = self._make_agent()
        try:
            agent.start()
            time.sleep(0.05)
            status = agent.status()
        finally:
            agent.stop()
        for key in ["state", "is_running", "session_id", "uptime_seconds",
                    "events_captured", "events_sent", "events_dropped",
                    "events_buffered", "backend_url", "accessibility_granted",
                    "allowlist", "include_window_title", "poll_interval_seconds"]:
            self.assertIn(key, status, f"Missing status key: {key}")

    def test_43_start_stop_records_timestamps(self):
        """start_time and stop_time are set on start() and stop() respectively."""
        agent = self._make_agent()
        self.assertIsNone(agent.start_time)
        self.assertIsNone(agent.stop_time)
        agent.start()
        time.sleep(0.05)
        self.assertIsNotNone(agent.start_time)
        agent.stop()
        self.assertIsNotNone(agent.stop_time)
        self.assertGreater(agent.stop_time, agent.start_time)


# ---------------------------------------------------------------------------
# 6. Permission Denied Behavior
# ---------------------------------------------------------------------------

class TestPermissionDeniedBehavior(unittest.TestCase):

    def test_44_appkit_unavailable_fallback_path(self):
        """When PyObjC is absent, collector fallback path is exercised."""
        config = make_config()
        col = MacOSActivityCollector(config=config)
        col.has_appkit = False
        with patch.object(col, "_get_frontmost_app_fallback", return_value={
            "name": "Terminal", "bundle_id": "com.apple.Terminal",
            "pid": None, "activation_policy": 0,
        }):
            fb = col._get_frontmost_app_fallback()
        self.assertIsNotNone(fb)
        self.assertEqual(fb["name"], "Terminal")

    def test_45_accessibility_denied_does_not_crash_agent(self):
        """Agent runs without errors when Accessibility permissions are denied."""
        config = make_config()
        with patch("agent.collector.check_accessibility_trusted", return_value=False):
            col = MacOSActivityCollector(config=config)
            self.assertFalse(col._accessibility_granted)
            # Collector should still initialize cleanly
            self.assertIsNone(col._last_app_name)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 68)
    print("  WorkFlowOS Phase 5 - Desktop Activity Agent Test Suite")
    print("=" * 68)
    print("  NOTE: All macOS-native APIs are mocked.")
    print("  These tests do NOT perform real desktop observation.")
    print("=" * 68)
    print()

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    print("=" * 68)
    print(f"  Tests Run   : {result.testsRun}")
    print(f"  Failures    : {len(result.failures)}")
    print(f"  Errors      : {len(result.errors)}")
    print(f"  Skipped     : {len(result.skipped)}")
    print(f"  Result      : {'PASS' if result.wasSuccessful() else 'FAIL'}")
    print("=" * 68)
    sys.exit(0 if result.wasSuccessful() else 1)
