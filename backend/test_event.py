#!/usr/bin/env python3
"""
WorkFlowOS Event Seeding and Testing Script
Sends sample events to the FastAPI backend (POST /api/events).
"""

import sys
import os
import json
import argparse
import requests
from datetime import datetime, timezone

DEFAULT_API_URL = os.getenv("API_URL", "http://localhost:8000/api/events")

# Exact primary demo event requested in specifications
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

# Diverse sample events for testing different actions & apps
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

def send_event(api_url: str, event_data: dict):
    print(f"\n[POST] -> {api_url}")
    print(f"Payload: {json.dumps(event_data, indent=2)}")
    try:
        response = requests.post(api_url, json=event_data, timeout=5)
        print(f"Status Code: {response.status_code}")
        if response.status_code in (200, 201):
            res_data = response.json()
            print(f"✓ Success! Created Event ID: {res_data.get('id')}")
            print(f"Response: {json.dumps(res_data, indent=2)}")
            return res_data
        else:
            print(f"✗ Failed ({response.status_code}): {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"✗ Connection error connecting to {api_url}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="WorkFlowOS Test Event Sender")
    parser.add_argument("--url", default=DEFAULT_API_URL, help=f"Backend API URL (default: {DEFAULT_API_URL})")
    parser.add_argument("--all", action="store_true", help="Send all sample events (open_email, download_attachment, search_customer, update_customer, send_message)")
    args = parser.parse_args()

    if args.all:
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
        print("\nTip: Run with '--all' to seed all 5 sample action events.")

if __name__ == "__main__":
    main()
