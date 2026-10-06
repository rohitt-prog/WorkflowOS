"""
WorkFlowOS Phase 12: Centralized Sensitive Data Redaction Engine

Provides deterministic, non-destructive sanitization and auditing of structured
and unstructured data across event ingestion, execution results, logs, and APIs.

Strict Invariants:
- Never mutates the caller's original data structure.
- Never logs, returns, or stores raw secrets.
- Deterministic heuristic matching (NO external AI, embeddings, or ML models).
- Preserves useful workflow structures (verbs, targets, normal parameters).
"""

import copy
import re
from typing import Any, Dict, List, Optional, Set, Tuple

# Bounded taxonomy of sensitive dictionary key identifiers
SENSITIVE_KEY_NAMES: Set[str] = {
    "password",
    "passwd",
    "secret",
    "client_secret",
    "api_key",
    "apikey",
    "token",
    "api_token",
    "access_token",
    "refresh_token",
    "auth_token",
    "oauth_token",
    "session_token",
    "bearer_token",
    "authorization",
    "cookie",
    "cookies",
    "set-cookie",
    "private_key",
    "privkey",
    "credential",
    "credentials",
    "cvv",
    "cvc",
    "security_code",
    "credit_card",
    "card_number",
    "cc_number",
    "bank_account",
    "routing_number",
    "ssn",
    "social_security",
}

# Substring matches on key names that reliably indicate sensitive credentials
_SENSITIVE_KEY_SUBSTRINGS: Tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "privkey",
    "credential",
    "client_secret",
)

# Regex to scrub bearer and basic authorization tokens from strings
_BEARER_REGEX = re.compile(r"\bBearer\s+([a-zA-Z0-9_\-\.\+\/=]{8,})", re.IGNORECASE)
_BASIC_REGEX = re.compile(r"\bBasic\s+([a-zA-Z0-9_\-\.\+\/=]{8,})", re.IGNORECASE)

# Scrub token/key-value pairs in unstructured text (e.g. error logs, query strings)
_KEY_VAL_SECRET_REGEX = re.compile(
    r"\b(token|access_token|refresh_token|secret|client_secret|password|passwd|api_key|apikey|private_key|cvv)\b(\s*(?:[:=]|is|was)?\s*)(['\"]?)([^\s'\"&,;]{3,})\3",
    re.IGNORECASE,
)

# Scrub recognizable platform token prefixes
_KNOWN_TOKEN_PREFIX_REGEX = re.compile(
    r"\b(ghp_[a-zA-Z0-9_]{15,}|gho_[a-zA-Z0-9_]{15,}|ghu_[a-zA-Z0-9_]{15,}|ghs_[a-zA-Z0-9_]{15,}|ghr_[a-zA-Z0-9_]{15,}|glpat-[a-zA-Z0-9_\-]{15,}|ya29\.[a-zA-Z0-9_\-]{15,}|sk-[a-zA-Z0-9_\-]{15,}|AIza[0-9A-Za-z\-_]{35}|AKIA[0-9A-Z]{16})\b"
)

# Scrub standard JSON Web Tokens (3 base64 segments)
_JWT_REGEX = re.compile(r"\beyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}\b")

# Scrub multi-line PEM private keys
_PEM_PRIVATE_KEY_REGEX = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
)

# Credit card candidate pattern: 13 to 19 digits with optional hyphens or spaces
_CARD_CANDIDATE_REGEX = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def _is_luhn_valid(candidate: str) -> bool:
    """Validates credit card checksum using the Luhn algorithm."""
    digits = re.sub(r"\D", "", candidate)
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    reverse_digits = digits[::-1]
    for i, char in enumerate(reverse_digits):
        d = int(char)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (total % 10 == 0)


def _scrub_credit_cards(text: str) -> str:
    """Scans text for sequences that pass the Luhn check and redacts them."""
    def _replacer(match: re.Match) -> str:
        matched_str = match.group(0)
        if _is_luhn_valid(matched_str):
            return "[REDACTED_CARD]"
        return matched_str

    return _CARD_CANDIDATE_REGEX.sub(_replacer, text)


def sanitize_log_message(message: str) -> str:
    """
    Scans unstructured log strings and exception text, scrubbing authorization headers,
    known platform secrets, PEM private keys, JWTs, and credit card numbers.
    """
    if not isinstance(message, str):
        return str(message) if message is not None else ""

    scrubbed = _PEM_PRIVATE_KEY_REGEX.sub("[REDACTED_PRIVATE_KEY]", message)
    scrubbed = _BEARER_REGEX.sub("Bearer [REDACTED]", scrubbed)
    scrubbed = _BASIC_REGEX.sub("Basic [REDACTED]", scrubbed)
    scrubbed = _KEY_VAL_SECRET_REGEX.sub(r"\1\2\3[REDACTED]\3", scrubbed)
    scrubbed = _KNOWN_TOKEN_PREFIX_REGEX.sub("[REDACTED]", scrubbed)
    scrubbed = _JWT_REGEX.sub("[REDACTED_JWT]", scrubbed)
    scrubbed = _scrub_credit_cards(scrubbed)
    return scrubbed


SAFE_METADATA_KEYS: Set[str] = {
    "requires_credentials",
    "credentials_available",
    "has_credentials",
    "requires_approval",
    "auth_requirements",
}


def is_sensitive_key(key: Any) -> bool:
    """Deterministically checks if a dictionary key represents sensitive data."""
    if not isinstance(key, str):
        key = str(key)
    key_lower = key.strip().lower()
    if key_lower in SAFE_METADATA_KEYS:
        return False
    if key_lower in SENSITIVE_KEY_NAMES:
        return True
    return any(sub in key_lower for sub in _SENSITIVE_KEY_SUBSTRINGS)


def redact_sensitive_data(data: Any, inplace: bool = False) -> Any:
    """
    Recursively redacts sensitive values in dicts, lists, and strings.

    Guarantees:
    - If inplace=False (default), leaves original data untouched and returns a sanitized copy.
    - Masks sensitive dict keys with '[REDACTED]'.
    - Scans string values for embedded tokens, bearer headers, and cards.
    - Traverses arbitrarily nested structures safely.
    """
    target = data if inplace else copy.deepcopy(data)
    return _redact_recursive(target)


def _redact_recursive(obj: Any) -> Any:
    if isinstance(obj, dict):
        cleaned: Dict[str, Any] = {}
        for k, v in obj.items():
            if is_sensitive_key(k):
                if isinstance(v, (dict, list)):
                    # Container under a sensitive grouping key (e.g. 'credentials', 'tokens') — recurse
                    cleaned[k] = _redact_recursive(v)
                else:
                    cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = _redact_recursive(v)
        return cleaned

    elif isinstance(obj, list):
        return [_redact_recursive(item) for item in obj]

    elif isinstance(obj, tuple):
        return tuple(_redact_recursive(item) for item in obj)

    elif isinstance(obj, set):
        return {_redact_recursive(item) for item in obj}

    elif isinstance(obj, str):
        return sanitize_log_message(obj)

    return obj


def audit_sensitive_data(data: Any, current_path: str = "") -> Dict[str, Any]:
    """
    Deterministically audits an object for sensitive information.
    Reports detected categories and field paths without leaking raw secrets.
    """
    detected_categories: Set[str] = set()
    redacted_fields: List[str] = []

    def _audit_walk(node: Any, path: str):
        if isinstance(node, dict):
            for k, v in node.items():
                field_path = f"{path}.{k}" if path else str(k)
                if is_sensitive_key(k):
                    k_lower = str(k).lower()
                    if any(c in k_lower for c in ("card", "cvv", "bank", "routing")):
                        detected_categories.add("FINANCIAL")
                    elif any(c in k_lower for c in ("token", "jwt", "bearer", "api_key", "apikey", "secret")):
                        detected_categories.add("AUTHENTICATION_TOKEN")
                    else:
                        detected_categories.add("AUTHENTICATION_CREDENTIAL")
                    redacted_fields.append(field_path)
                else:
                    _audit_walk(v, field_path)

        elif isinstance(node, list):
            for idx, item in enumerate(node):
                _audit_walk(item, f"{path}[{idx}]")

        elif isinstance(node, str):
            # Check string content for embedded secrets
            if _BEARER_REGEX.search(node) or _BASIC_REGEX.search(node):
                detected_categories.add("AUTHENTICATION_HEADER")
                redacted_fields.append(path or "string_header")
            if _KNOWN_TOKEN_PREFIX_REGEX.search(node) or _JWT_REGEX.search(node) or _PEM_PRIVATE_KEY_REGEX.search(node):
                detected_categories.add("EMBEDDED_SECRET_TOKEN")
                redacted_fields.append(path or "string_token")
            if _CARD_CANDIDATE_REGEX.search(node):
                for match in _CARD_CANDIDATE_REGEX.finditer(node):
                    if _is_luhn_valid(match.group(0)):
                        detected_categories.add("FINANCIAL_CARD")
                        redacted_fields.append(path or "string_card")
                        break

    _audit_walk(data, current_path)

    return {
        "contains_sensitive_data": len(redacted_fields) > 0,
        "detected_categories": sorted(list(detected_categories)),
        "redacted_fields": sorted(list(set(redacted_fields))),
    }
