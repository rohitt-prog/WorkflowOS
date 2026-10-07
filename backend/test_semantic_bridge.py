"""
WorkFlowOS — Semantic Event Bridge & Discovery Integration Test

Verifies the full pipeline:
REAL USER DEMO ACTION
  ↓
SEMANTIC EVENT (open_email, download_attachment, search_customer, update_customer, send_message)
  ↓
POST /api/events
  ↓
FastAPI Ingestion & Privacy Gate
  ↓
MongoDB Storage
  ↓
GET /api/events verification (session_id continuity, canonical verbs, metadata)
  ↓
GET /api/discovery/repeated pattern discovery
"""

import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
import mongomock_motor

from backend.main import app
import backend.database as db_mod
from discovery.service import discovery_service


class TestSemanticEventBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure in-memory mock client for clean isolated testing
        cls.mock_client = mongomock_motor.AsyncMongoMockClient()
        db_mod._mongo_client = cls.mock_client
        db_mod._database = cls.mock_client["workflowos"]
        cls.client = TestClient(app)

    def setUp(self):
        # Reset collections between tests
        import asyncio
        db = db_mod.get_database()
        asyncio.run(db["events"].drop())

    def test_semantic_event_ingestion_and_discovery_pipeline(self):
        """
        Simulate the exact user flow across the 3 demo applications:
        1. /demo/email -> open_email
        2. /demo/email -> download_attachment
        3. /demo/crm   -> search_customer
        4. /demo/crm   -> update_customer
        5. /demo/chat  -> send_message
        All sharing a stable browser session ID.
        """
        session_1 = "workflowos_demo_session_tab_alpha"
        now = datetime.now(timezone.utc)

        events_sequence_1 = [
            {
                "session_id": session_1,
                "timestamp": (now + timedelta(seconds=1)).isoformat(),
                "application": "demo_email",
                "event_type": "open_email",
                "target": "customer_request",
                "metadata": {"email_id": "email_001", "customer": "Rahul"},
            },
            {
                "session_id": session_1,
                "timestamp": (now + timedelta(seconds=2)).isoformat(),
                "application": "demo_email",
                "event_type": "download_attachment",
                "target": "customer_request",
                "metadata": {"email_id": "email_001", "attachment": "customer_request.pdf"},
            },
            {
                "session_id": session_1,
                "timestamp": (now + timedelta(seconds=3)).isoformat(),
                "application": "demo_crm",
                "event_type": "search_customer",
                "target": "customer_request",
                "metadata": {"customer": "Rahul", "query": "rahul"},
            },
            {
                "session_id": session_1,
                "timestamp": (now + timedelta(seconds=4)).isoformat(),
                "application": "demo_crm",
                "event_type": "update_customer",
                "target": "customer_request",
                "metadata": {"customer": "Rahul", "status": "Active", "tier": "Enterprise VIP"},
            },
            {
                "session_id": session_1,
                "timestamp": (now + timedelta(seconds=5)).isoformat(),
                "application": "demo_chat",
                "event_type": "send_message",
                "target": "customer_request",
                "metadata": {"channel": "#customer-support"},
            },
        ]

        # 1. Post all 5 semantic events to /api/events
        for ev in events_sequence_1:
            resp = self.client.post("/api/events", json=ev)
            self.assertEqual(resp.status_code, 201, f"Failed to ingest event {ev['event_type']}: {resp.text}")
            data = resp.json()
            self.assertEqual(data["session_id"], session_1)
            self.assertEqual(data["event_type"], ev["event_type"])
            self.assertEqual(data["application"], ev["application"])

        # 2. Query GET /api/events and verify retrieval
        resp_get = self.client.get(f"/api/events?session_id={session_1}")
        self.assertEqual(resp_get.status_code, 200)
        retrieved_events = resp_get.json()
        self.assertEqual(len(retrieved_events), 5)

        # Reverse since /api/events returns newest first (descending timestamp)
        chronological_events = list(reversed(retrieved_events))
        expected_verbs = [
            "open_email",
            "download_attachment",
            "search_customer",
            "update_customer",
            "send_message",
        ]
        retrieved_verbs = [e["event_type"] for e in chronological_events]
        self.assertEqual(retrieved_verbs, expected_verbs)

        # Verify all five events share the same session ID
        for e in chronological_events:
            self.assertEqual(e["session_id"], session_1)

        # 3. Simulate Session 2 executing the identical routine to satisfy multi-session repetition criteria (min_occurrences >= 2)
        session_2 = "workflowos_demo_session_tab_beta"
        for i, ev in enumerate(events_sequence_1):
            ev2 = dict(ev)
            ev2["session_id"] = session_2
            ev2["timestamp"] = (now + timedelta(seconds=10 + i)).isoformat()
            resp2 = self.client.post("/api/events", json=ev2)
            self.assertEqual(resp2.status_code, 201)

        # 4. Trigger Discovery endpoint GET /api/discovery/repeated
        resp_disc = self.client.get("/api/discovery/repeated")
        self.assertEqual(resp_disc.status_code, 200)
        disc_data = resp_disc.json()

        self.assertTrue(disc_data["detected"], "Workflow discovery must detect the repeated sequence")
        self.assertGreaterEqual(len(disc_data["workflows"]), 1, "Must find at least 1 discovered workflow")

        # Find the canonical 5-step customer request processing workflow
        matched_wf = None
        for wf in disc_data["workflows"]:
            if wf["sequence"] == expected_verbs:
                matched_wf = wf
                break

        self.assertIsNotNone(
            matched_wf,
            f"Expected canonical sequence {expected_verbs} to be discovered. Found sequences: {[w['sequence'] for w in disc_data['workflows']]}"
        )
        self.assertEqual(matched_wf["occurrences"], 2)
        self.assertIn(session_1, matched_wf["session_ids"])
        self.assertIn(session_2, matched_wf["session_ids"])
        self.assertGreaterEqual(matched_wf["confidence"], 0.70)
        print("\n[VERIFICATION SUCCESSFUL]")
        print(f"  Discovered workflow title: {matched_wf.get('title')}")
        print(f"  Sequence: {' -> '.join(matched_wf['sequence'])}")
        print(f"  Occurrences: {matched_wf['occurrences']} across sessions: {matched_wf['session_ids']}")
        print(f"  Confidence: {matched_wf['confidence']:.4f}")


if __name__ == "__main__":
    unittest.main()
