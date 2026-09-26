#!/usr/bin/env python3
"""
WorkFlowOS Event Seeding and Testing Script

Sends sample events to the FastAPI backend (POST /api/events).

Usage:
  python backend/test_event.py                  # Send single demo event
  python backend/test_event.py --all            # Send 5 events for demo_session
  python backend/test_event.py --seed-workflows # Seed 3 repeated sessions for Phase 2 discovery
"""

import sys
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
# Phase 1: diverse sample events (single session)
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
    {
        "session_id": "demo_session",
        "timestamp": "2026-09-26T10:33:45Z",
        "application": "demo_crm",
        "event_type": "update_customer",
        "target": "Rahul Sharma",
        "metadata": {
            "field_updated": "tier",
            "old_value": "standard",
            "new_value": "enterprise"
        }
    },
    {
        "session_id": "demo_session",
        "timestamp": "2026-09-26T10:35:10Z",
        "application": "demo_messaging",
        "event_type": "send_message",
        "target": "#client-support",
        "metadata": {
            "channel": "slack",
            "text": "Enterprise account tier updated for Rahul Sharma"
        }
    }
]

# ---------------------------------------------------------------------------
# Phase 2: Workflow Discovery seed data — 3 sessions with identical sequences
#           Uses different customers but same event_type order.
#           Timestamps are spaced naturally per session.
# ---------------------------------------------------------------------------

def _make_workflow_session(session_id: str, customer_name: str, base_iso: str) -> list:
    """
    Build the canonical 5-event 'Customer Request Processing' workflow
    for a given session, customer, and base timestamp.
    Events are spaced 1-2 minutes apart to simulate realistic activity.
    """
    base = datetime.fromisoformat(base_iso.replace("Z", "+00:00"))
    first_name = customer_name.split()[0]
    last_name = customer_name.split()[1] if len(customer_name.split()) > 1 else ""
    email = f"{first_name.lower()}@example.com"

    return [
        {
            "session_id": session_id,
            "timestamp": (base + timedelta(minutes=0)).isoformat().replace("+00:00", "Z"),
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
            "timestamp": (base + timedelta(minutes=1, seconds=15)).isoformat().replace("+00:00", "Z"),
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
            "timestamp": (base + timedelta(minutes=2)).isoformat().replace("+00:00", "Z"),
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
            "timestamp": (base + timedelta(minutes=3, seconds=45)).isoformat().replace("+00:00", "Z"),
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
            "timestamp": (base + timedelta(minutes=5, seconds=10)).isoformat().replace("+00:00", "Z"),
            "application": "demo_messaging",
            "event_type": "send_message",
            "target": "#client-support",
            "metadata": {
                "channel": "slack",
                "text": f"Enterprise tier updated for {customer_name}"
            }
        },
    ]


# Phase 2 workflow seed: 3 sessions, same sequence, different customers
WORKFLOW_SESSIONS = [
    _make_workflow_session("session_001", "Rahul Sharma", "2026-09-26T09:00:00Z"),
    _make_workflow_session("session_002", "Priya Patel", "2026-09-26T10:15:00Z"),
    _make_workflow_session("session_003", "Amit Verma", "2026-09-26T11:30:00Z"),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def send_event(api_url: str, event_data: dict) -> dict | None:
    print(f"\n[POST] -> {api_url}")
    print(f"Payload: {json.dumps(event_data, indent=2)}")
    try:
        response = requests.post(api_url, json=event_data, timeout=5)
        print(f"Status Code: {response.status_code}")
        if response.status_code in (200, 201):
            res_data = response.json()
            print(f"✓ Success! Created Event ID: {res_data.get('id')}")
            return res_data
        else:
            print(f"✗ Failed ({response.status_code}): {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"✗ Connection error connecting to {api_url}: {e}")
        return None


def seed_workflow_sessions(api_url: str) -> None:
    """
    Seeds 3 sessions with the identical 5-event workflow sequence into MongoDB
    so that GET /api/discovery/repeated returns a detected repeated workflow.

    IMPORTANT: This is NOT run automatically on startup.
               Call explicitly via: python backend/test_event.py --seed-workflows
    """
    total = sum(len(s) for s in WORKFLOW_SESSIONS)
    print(f"\n{'='*60}")
    print("  Phase 2 Workflow Discovery Seed")
    print(f"  Seeding {len(WORKFLOW_SESSIONS)} sessions × 5 events = {total} events total")
    print(f"{'='*60}")

    success_count = 0
    for session_events in WORKFLOW_SESSIONS:
        session_id = session_events[0]["session_id"]
        customer = session_events[0]["metadata"].get("customer", "?")
        print(f"\n--- Session: {session_id} | Customer: {customer} ---")
        for ev in session_events:
            res = send_event(api_url, ev)
            if res:
                success_count += 1

    print(f"\n{'='*60}")
    print(f"  Seed complete: {success_count}/{total} events created successfully.")
    print(f"  Now call GET /api/discovery/repeated to detect the workflow.")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="WorkFlowOS Test Event Sender",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backend/test_event.py                   Send single demo event
  python backend/test_event.py --all             Send 5 events (Phase 1 demo_session)
  python backend/test_event.py --seed-workflows  Seed 3 sessions for Phase 2 discovery
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
        help="Send all 5 Phase 1 sample events (single demo_session)"
    )
    parser.add_argument(
        "--seed-workflows",
        action="store_true",
        help="Seed 3 repeated sessions for Phase 2 workflow discovery testing"
    )
    args = parser.parse_args()

    if args.seed_workflows:
        seed_workflow_sessions(args.url)
    elif args.all:
        print(f"--- Sending {len(SAMPLE_EVENTS)} Sample Events to {args.url} ---")
        success_count = 0
        for ev in SAMPLE_EVENTS:
            res = send_event(args.url, ev)
            if res:
                success_count += 1
        print(f"\nCompleted: {success_count}/{len(SAMPLE_EVENTS)} events created successfully.")
    else:
        print(f"--- Sending Primary Demo Event to {args.url} ---")
        send_event(args.url, PRIMARY_DEMO_EVENT)
        print("\nTip: Run with '--all' to seed all 5 Phase 1 events.")
        print("Tip: Run with '--seed-workflows' to seed Phase 2 discovery data.")


if __name__ == "__main__":
    main()
