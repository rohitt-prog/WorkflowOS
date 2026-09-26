#!/usr/bin/env python3
"""
WorkFlowOS Event Seeding and Testing Script

Sends sample events to the FastAPI backend (POST /api/events).

Usage:
  python backend/test_event.py                  # Send single demo event
  python backend/test_event.py --all            # Send 5 events for demo_session
  python backend/test_event.py --seed-workflows # Idempotent: seed 3 repeated sessions for Phase 2
"""

import os
import json
import argparse
import requests
from datetime import datetime, timezone, timedelta

DEFAULT_API_URL = os.getenv("API_URL", "http://localhost:8000/api/events")

# ---------------------------------------------------------------------------
# Primary single demo event (Phase 1 spec)
# ---------------------------------------------------------------------------

PRIMARY_DEMO_EVENT = {
    "session_id": "demo_session",
    "timestamp": "2026-09-26T10:30:00Z",
    "application": "demo_email",
    "event_type": "open_email",
    "target": "customer_request",
    "metadata": {
        "customer": "Rahul"
    }
}

# ---------------------------------------------------------------------------
# Phase 1: diverse sample events (single demo_session)
#
# IMPORTANT — similarity guard:
#   The Phase 2 canonical workflow has 5 steps. difflib.SequenceMatcher
#   gives a 4-step prefix a similarity of 0.889 — above the default 0.8
#   detection threshold — which would cause demo_session to appear as a
#   false 4th occurrence in the discovery results.
#
#   demo_session intentionally uses only 3 steps (similarity = 0.75 to the
#   5-step canonical, safely below 0.8) so it is never incorrectly grouped
#   with the Phase 2 workflow sessions.
# ---------------------------------------------------------------------------

SAMPLE_EVENTS = [
    {
        "session_id": "demo_session",
        "timestamp": "2026-09-26T10:30:00Z",
        "application": "demo_email",
        "event_type": "open_email",
        "target": "customer_request",
        "metadata": {
            "customer": "Rahul",
            "subject": "Urgent pricing inquiry"
        }
    },
    {
        "session_id": "demo_session",
        "timestamp": "2026-09-26T10:31:15Z",
        "application": "demo_email",
        "event_type": "download_attachment",
        "target": "invoice_req_rahul.pdf",
        "metadata": {
            "file_size_kb": 245,
            "sender": "rahul@example.com"
        }
    },
    {
        "session_id": "demo_session",
        "timestamp": "2026-09-26T10:32:00Z",
        "application": "demo_crm",
        "event_type": "search_customer",
        "target": "Rahul Sharma",
        "metadata": {
            "search_query": "Rahul",
            "matched_records": 1
        }
    },
    # demo_session stops here (3 steps, similarity=0.75 vs 5-step canonical).
    # Do NOT add update_customer or send_message to this session.
]

# ---------------------------------------------------------------------------
# Phase 2: Workflow Discovery seed data — 3 sessions, identical 5-event
#           sequence, different customers, strictly increasing timestamps.
#
# IMPORTANT:
#   --seed-workflows is idempotent:
#     it deletes session_001/002/003 events before re-inserting them.
#     It does NOT touch demo_session or any other data.
# ---------------------------------------------------------------------------

# These are the canonical session IDs managed by --seed-workflows.
SEED_SESSION_IDS = ["session_001", "session_002", "session_003"]


def _make_workflow_session(session_id: str, customer_name: str, base_iso: str) -> list:
    """
    Builds the canonical 5-event 'Customer Request Processing' sequence
    for a session. All timestamps are strictly increasing from base_iso.

    Sequence:
      open_email → download_attachment → search_customer → update_customer → send_message
    """
    base = datetime.fromisoformat(base_iso.replace("Z", "+00:00"))
    first_name = customer_name.split()[0]
    email = f"{first_name.lower()}@example.com"

    return [
        {
            "session_id": session_id,
            "timestamp": (base + timedelta(minutes=0)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "application": "demo_email",
            "event_type": "open_email",
            "target": "customer_request",
            "metadata": {
                "customer": customer_name,
                "subject": f"Request from {first_name}"
            }
        },
        {
            "session_id": session_id,
            "timestamp": (base + timedelta(minutes=1, seconds=15)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "application": "demo_email",
            "event_type": "download_attachment",
            "target": f"invoice_{first_name.lower()}.pdf",
            "metadata": {
                "file_size_kb": 198,
                "sender": email
            }
        },
        {
            "session_id": session_id,
            "timestamp": (base + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "application": "demo_crm",
            "event_type": "search_customer",
            "target": customer_name,
            "metadata": {
                "search_query": first_name,
                "matched_records": 1
            }
        },
        {
            "session_id": session_id,
            "timestamp": (base + timedelta(minutes=3, seconds=45)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "application": "demo_crm",
            "event_type": "update_customer",
            "target": customer_name,
            "metadata": {
                "field_updated": "tier",
                "old_value": "standard",
                "new_value": "enterprise"
            }
        },
        {
            "session_id": session_id,
            "timestamp": (base + timedelta(minutes=5, seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "application": "demo_messaging",
            "event_type": "send_message",
            "target": "#client-support",
            "metadata": {
                "channel": "slack",
                "text": f"Enterprise tier updated for {customer_name}"
            }
        },
    ]


# Build WORKFLOW_SESSIONS at module load — deterministic, no side effects.
WORKFLOW_SESSIONS = [
    _make_workflow_session("session_001", "Rahul Sharma",  "2026-09-26T09:00:00Z"),
    _make_workflow_session("session_002", "Priya Patel",   "2026-09-26T10:15:00Z"),
    _make_workflow_session("session_003", "Amit Verma",    "2026-09-26T11:30:00Z"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_api_url(api_url: str) -> str:
    """Strip /api/events suffix to get the root backend URL."""
    return api_url.replace("/api/events", "").rstrip("/")


def send_event(api_url: str, event_data: dict) -> dict | None:
    print(f"\n  [POST] {api_url}")
    print(f"  Payload: {json.dumps(event_data, indent=4)}")
    try:
        response = requests.post(api_url, json=event_data, timeout=5)
        print(f"  Status: {response.status_code}")
        if response.status_code in (200, 201):
            res_data = response.json()
            print(f"  ✓ Created Event ID: {res_data.get('id')}")
            return res_data
        else:
            print(f"  ✗ Failed: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Connection error: {e}")
        return None


def delete_session(base_url: str, session_id: str) -> int:
    """
    Calls DELETE /api/events/session/{session_id} to remove stale seed data
    for a specific session. Returns the number of deleted events.
    """
    url = f"{base_url}/api/events/session/{session_id}"
    try:
        r = requests.delete(url, timeout=5)
        if r.status_code == 200:
            deleted = r.json().get("deleted_count", 0)
            print(f"  ↩  Cleared {deleted} existing events for '{session_id}'")
            return deleted
        else:
            print(f"  ⚠  Delete returned {r.status_code} for session '{session_id}': {r.text}")
            return 0
    except requests.exceptions.RequestException as e:
        print(f"  ⚠  Could not reach DELETE endpoint: {e}")
        return 0


# ---------------------------------------------------------------------------
# Seeding logic
# ---------------------------------------------------------------------------

def seed_workflow_sessions(api_url: str) -> None:
    """
    Idempotent seeding of 3 sessions (session_001/002/003) for Phase 2
    workflow discovery testing.

    Steps:
      1. DELETE existing events for each of the 3 seed sessions only.
         (demo_session and any other data are left untouched.)
      2. POST 5 fresh events per session with strictly increasing timestamps.

    Run this explicitly:
      python backend/test_event.py --seed-workflows
    """
    base_url = _base_api_url(api_url)
    total_events = sum(len(s) for s in WORKFLOW_SESSIONS)

    print(f"\n{'='*64}")
    print("  Phase 2 Workflow Discovery Seed  (idempotent)")
    print(f"  Sessions : {', '.join(SEED_SESSION_IDS)}")
    print(f"  Events   : {len(WORKFLOW_SESSIONS)} sessions × 5 = {total_events} total")
    print(f"{'='*64}")

    # Step 1: Clear only the 3 seed sessions to avoid duplicates.
    print("\n[1/2] Clearing existing seed session data...")
    for sid in SEED_SESSION_IDS:
        delete_session(base_url, sid)

    # Step 2: Insert fresh events.
    print("\n[2/2] Inserting clean seed events...")
    success = 0
    for session_events in WORKFLOW_SESSIONS:
        sid = session_events[0]["session_id"]
        customer = session_events[0]["metadata"].get("customer", "?")
        print(f"\n  --- {sid} | {customer} ---")
        for ev in session_events:
            res = send_event(api_url, ev)
            if res:
                success += 1

    print(f"\n{'='*64}")
    print(f"  Seed complete: {success}/{total_events} events created.")
    print(f"  Run: curl http://localhost:8000/api/discovery/repeated")
    print(f"{'='*64}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="WorkFlowOS Test Event Sender",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backend/test_event.py                   Single demo event (Phase 1)
  python backend/test_event.py --all             5-event Phase 1 demo_session
  python backend/test_event.py --seed-workflows  Idempotent Phase 2 seed (3 sessions)
"""
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_API_URL,
        help=f"Backend API URL (default: {DEFAULT_API_URL})"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Send all Phase 1 sample events (demo_session, 4 events)"
    )
    parser.add_argument(
        "--seed-workflows",
        action="store_true",
        help=(
            "Idempotent: delete then re-insert session_001/002/003 "
            "with the 5-step Phase 2 workflow sequence. "
            "Does NOT touch demo_session."
        )
    )
    args = parser.parse_args()

    if args.seed_workflows:
        seed_workflow_sessions(args.url)
    elif args.all:
        print(f"--- Sending {len(SAMPLE_EVENTS)} Phase 1 events to {args.url} ---")
        ok = sum(1 for ev in SAMPLE_EVENTS if send_event(args.url, ev))
        print(f"\nCompleted: {ok}/{len(SAMPLE_EVENTS)} events created.")
    else:
        print(f"--- Sending primary demo event to {args.url} ---")
        send_event(args.url, PRIMARY_DEMO_EVENT)
        print("\nTip: --all seeds 4 Phase 1 events.")
        print("Tip: --seed-workflows seeds 3 Phase 2 discovery sessions.")


if __name__ == "__main__":
    main()
