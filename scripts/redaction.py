#!/usr/bin/env python3
"""Shared high-confidence secret detection and report redaction helpers."""

import re

# Conservative credential shapes used by scan diagnostics and eval artifact
# minimization. Keep this list single-sourced: persisted/report text must redact
# exactly the values the scanner calls high-confidence secrets.
SECRET_PATTERNS = [
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("Stripe secret key", re.compile(r"\b[sr]k_live_[0-9A-Za-z]{16,}\b")),
    ("JSON Web Token", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    (
        "Generic hardcoded secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret(?:[_-]?key)?|access[_-]?key|client[_-]?secret|token|password|passwd|"
            r"auth[_-]?token|bearer)\b\s*[:=]\s*"
            r"(?:['\"][^'\"\s]{12,}['\"]|(?P<unquoted>[A-Za-z0-9+/_\-.]{16,}))"
        ),
    ),
]

_SECRET_PLACEHOLDER_RE = re.compile(
    r"\byour[_-]|\bmy[_-]|\bexample\b|\bsample\b|\bdummy\b|\bplaceholder\b|\bchangeme\b|"
    r"\bxxx|\binsert[_-]|\bredacted\b|\bhere\b|<[^<>]*>|\$\{",
    re.I,
)

# An unquoted, purely alphabetic, mixed-case value is a code identifier — a
# typed-language annotation such as `token: CancellationToken` or a camelCase
# reference — not a credential: real secrets of this length are high-entropy
# and virtually always carry digits or symbols. Found scanning microsoft/vscode
# (benchmark corpus), whose Copilot-extension AGENTS.md documents TypeScript
# signatures like `handle(..., token: CancellationToken)`. Quoted values keep
# full recall: quoting asserts a literal value, not an identifier.
_IDENTIFIER_VALUE_RE = re.compile(r"^[A-Za-z]+$")


def is_identifier_annotation(match):
    """Whether a ``SECRET_PATTERNS`` match captured a code identifier, not a value.

    Accepts matches from the str patterns above or from scan.py's byte-compiled
    copies (the ``unquoted`` group name survives byte compilation), so the
    in-memory and streaming security paths share one predicate.
    """
    value = match.groupdict().get("unquoted")
    if not value:
        return False
    if isinstance(value, bytes):
        try:
            value = value.decode("ascii")
        except UnicodeDecodeError:
            return False
    return bool(
        _IDENTIFIER_VALUE_RE.match(value)
        and value != value.lower()
        and value != value.upper()
    )


def _is_exempt(match):
    """Whether a raw pattern match is a placeholder/identifier, not a secret."""
    return bool(_SECRET_PLACEHOLDER_RE.search(match.group(0))) or is_identifier_annotation(match)


def secret_hits(text):
    """Return labels for non-placeholder high-confidence secrets in ``text``."""
    hits = []
    for label, pattern in SECRET_PATTERNS:
        if any(not _is_exempt(match) for match in pattern.finditer(str(text))):
            hits.append(label)
    return hits


def redact_secret_values(text):
    """Replace complete secret spans while retaining placeholder examples."""
    redacted = str(text)
    for label, pattern in SECRET_PATTERNS:
        redacted = pattern.sub(
            lambda match: (
                match.group(0) if _is_exempt(match) else f"<redacted:{label}>"
            ),
            redacted,
        )
    return redacted
