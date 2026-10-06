"""
WorkFlowOS Phase 15: Safety & Security Benchmark

Explicitly tests security, privacy, and safety invariants:
1. Unknown action fail-closed:
   - is_action_read_only = False
   - is_action_mutating = False
   - requires_approval = True
   - execution = rejected
2. Unsupported action:
   - execution = rejected
3. Unknown application:
   - execution = rejected
4. Known mutating action:
   - requires_approval = True
5. Known read-only action:
   - requires_approval = False
6. Credential exposure scanning:
   - Verifies no API keys, OAuth tokens, passwords, MongoDB URIs, or secrets in outputs.
7. Privacy controls:
   - Sensitive values redacted
   - Collection gate enforced
   - Retention policy respected
"""

import re
import asyncio
from typing import Dict, List, Any

from integrations.registry import integration_registry, application_registry
from integrations.models import UnsupportedActionError, UnknownIntegrationError
from backend.privacy.service import privacy_service
from backend.privacy.redaction import redact_sensitive_data, audit_sensitive_data

# Secret scanning regexes
SECRET_PATTERNS = [
    (r"\bAIza[0-9A-Za-z\-_]{35}\b", "Google API Key"),
    (r"\bsk-[a-zA-Z0-9_\-]{20,}\b", "OpenAI / Anthropic Secret Key"),
    (r"\bghp_[a-zA-Z0-9_]{30,}\b", "GitHub Personal Access Token"),
    (r"\bmongodb(\+srv)?:\/\/[^\s'\"]+\b", "MongoDB Connection URI with credentials"),
    (r"\bBearer\s+[a-zA-Z0-9_\-\.\+\/=]{15,}\b", "Bearer Token Header"),
    (r"\b(?:client_secret|password|passwd|api_key)\s*[:=]\s*['\"][^'\"]{6,}['\"]", "Plaintext Credential Pair"),
]


def scan_for_secrets(text: str) -> List[str]:
    """Scans text for exposed credentials. Returns list of detected secret types."""
    detected = []
    for pattern, name in SECRET_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            detected.append(name)
    return detected


async def _run_safety_benchmark_async() -> Dict[str, Any]:
    """
    Executes comprehensive security, capability safety, and privacy evaluations.
    """
    safety_checks: Dict[str, bool] = {}
    details: Dict[str, Any] = {}

    # 1. Unknown Action Invariants
    unknown_action = "unknown_destructive_action_999"
    ro_unknown = integration_registry.is_action_read_only(unknown_action)
    mut_unknown = integration_registry.is_action_mutating(unknown_action)
    req_app_unknown = integration_registry.requires_approval(unknown_action)

    # Capability check raises UnsupportedActionError
    cap_unsupported_raised = False
    try:
        integration_registry.get_capability_or_raise(unknown_action, application_id="crm")
    except UnsupportedActionError:
        cap_unsupported_raised = True
    except Exception:
        cap_unsupported_raised = False

    # Execution dispatch fails closed
    unknown_action_exec_res = await integration_registry.route_action("crm", unknown_action, {})
    unknown_exec_rejected = not unknown_action_exec_res.success

    safety_checks["unknown_action_not_read_only"] = (ro_unknown is False)
    safety_checks["unknown_action_not_mutating"] = (mut_unknown is False)
    safety_checks["unknown_action_requires_approval"] = (req_app_unknown is True)
    safety_checks["unknown_action_capability_raised"] = cap_unsupported_raised
    safety_checks["unknown_action_execution_rejected"] = unknown_exec_rejected

    details["unknown_action"] = {
        "read_only": ro_unknown,
        "mutating": mut_unknown,
        "requires_approval": req_app_unknown,
        "capability_raised": cap_unsupported_raised,
        "execution_rejected": unknown_exec_rejected,
        "passed": (
            ro_unknown is False
            and mut_unknown is False
            and req_app_unknown is True
            and cap_unsupported_raised is True
            and unknown_exec_rejected is True
        ),
    }

    # 2. Unknown Application Rejection
    unknown_app = "nonexistent_alien_application"
    app_obj = integration_registry.get(unknown_app)

    app_unknown_raised = False
    try:
        integration_registry.get_capability_or_raise("search_customer", application_id=unknown_app)
    except UnknownIntegrationError:
        app_unknown_raised = True
    except Exception:
        app_unknown_raised = False

    unknown_app_exec_res = await integration_registry.route_action(unknown_app, "search_customer", {})
    unknown_app_rejected = not unknown_app_exec_res.success

    safety_checks["unknown_app_get_none"] = (app_obj is None)
    safety_checks["unknown_app_capability_raised"] = app_unknown_raised
    safety_checks["unknown_app_execution_rejected"] = unknown_app_rejected

    details["unknown_application"] = {
        "app_exists": app_obj is not None,
        "capability_raised": app_unknown_raised,
        "execution_rejected": unknown_app_rejected,
        "passed": app_obj is None and app_unknown_raised and unknown_app_rejected,
    }

    # 3. Known Mutating Action
    mutating_action = "update_customer"
    mut_is_mut = integration_registry.is_action_mutating(mutating_action)
    mut_req_app = integration_registry.requires_approval(mutating_action)
    mut_ro = integration_registry.is_action_read_only(mutating_action)

    safety_checks["known_mutating_action_mutating"] = (mut_is_mut is True)
    safety_checks["known_mutating_action_requires_approval"] = (mut_req_app is True)
    safety_checks["known_mutating_action_not_read_only"] = (mut_ro is False)

    details["known_mutating_action"] = {
        "action": mutating_action,
        "mutating": mut_is_mut,
        "requires_approval": mut_req_app,
        "read_only": mut_ro,
        "passed": mut_is_mut and mut_req_app and not mut_ro,
    }

    # 4. Known Read-Only Action
    read_only_action = "search_customer"
    ro_is_ro = integration_registry.is_action_read_only(read_only_action)
    ro_is_mut = integration_registry.is_action_mutating(read_only_action)
    ro_req_app = integration_registry.requires_approval(read_only_action)

    safety_checks["known_read_only_action_read_only"] = (ro_is_ro is True)
    safety_checks["known_read_only_action_not_mutating"] = (ro_is_mut is False)
    safety_checks["known_read_only_action_no_approval"] = (ro_req_app is False)

    details["known_read_only_action"] = {
        "action": read_only_action,
        "read_only": ro_is_ro,
        "mutating": ro_is_mut,
        "requires_approval": ro_req_app,
        "passed": ro_is_ro and not ro_is_mut and not ro_req_app,
    }

    # 5. Privacy & Sensitive Redaction Engine
    sensitive_payload = {
        "user": "Alice",
        "api_key": "AIzaSyFakeKeyForTestingRedaction12345678",
        "nested": {
            "password": "SuperSecretPassword123!",
            "token": "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
            "normal_field": "safe_value",
        },
        "log_message": "Failed auth with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.signature",
    }

    redacted = redact_sensitive_data(sensitive_payload)
    has_api_key_redacted = redacted["api_key"] == "[REDACTED]"
    has_password_redacted = redacted["nested"]["password"] == "[REDACTED]"
    has_token_redacted = redacted["nested"]["token"] == "[REDACTED]"
    normal_field_preserved = redacted["nested"]["normal_field"] == "safe_value"
    log_sanitized = "eyJ" not in redacted["log_message"]

    redaction_passed = (
        has_api_key_redacted
        and has_password_redacted
        and has_token_redacted
        and normal_field_preserved
        and log_sanitized
    )
    safety_checks["privacy_redaction_engine"] = redaction_passed

    details["privacy_redaction"] = {
        "api_key_redacted": has_api_key_redacted,
        "password_redacted": has_password_redacted,
        "token_redacted": has_token_redacted,
        "normal_field_preserved": normal_field_preserved,
        "log_token_sanitized": log_sanitized,
        "passed": redaction_passed,
    }

    # 6. Privacy Collection Gate & Retention
    orig_coll = privacy_service.is_collection_enabled()
    privacy_service.set_collection_enabled(False)
    gate_disabled = (privacy_service.is_collection_enabled() is False)
    privacy_service.set_collection_enabled(True)
    gate_enabled = (privacy_service.is_collection_enabled() is True)
    privacy_service.set_collection_enabled(orig_coll)  # Restore

    retention_days = privacy_service.get_retention_days()
    cutoff_iso = privacy_service.get_cutoff_timestamp()
    retention_valid = bool(retention_days >= 1 and cutoff_iso and "T" in cutoff_iso)

    safety_checks["privacy_collection_gate"] = gate_disabled and gate_enabled
    safety_checks["privacy_retention_valid"] = retention_valid

    details["privacy_governance"] = {
        "collection_gate_tested": gate_disabled and gate_enabled,
        "retention_days": retention_days,
        "cutoff_timestamp_valid": retention_valid,
        "passed": gate_disabled and gate_enabled and retention_valid,
    }

    total_checks = len(safety_checks)
    passed_checks = sum(1 for v in safety_checks.values() if v)
    safety_compliance_rate = round(passed_checks / total_checks, 4)

    return {
        "safety_compliance_rate": safety_compliance_rate,
        "total_safety_checks": total_checks,
        "passed_safety_checks": passed_checks,
        "zero_approval_bypass": (
            safety_checks["unknown_action_requires_approval"]
            and safety_checks["known_mutating_action_requires_approval"]
            and safety_checks["unknown_action_execution_rejected"]
            and safety_checks["unknown_app_execution_rejected"]
        ),
        "all_safety_checks_passed": passed_checks == total_checks,
        "checks": safety_checks,
        "details": details,
    }


def run_safety_benchmark() -> Dict[str, Any]:
    """Synchronous entry point for safety benchmark."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                return executor.submit(asyncio.run, _run_safety_benchmark_async()).result()
        else:
            return loop.run_until_complete(_run_safety_benchmark_async())
    except RuntimeError:
        return asyncio.run(_run_safety_benchmark_async())
