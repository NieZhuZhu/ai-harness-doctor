#!/usr/bin/env python3
"""Shared high-confidence secret detection and report redaction helpers."""

import re

# Conservative credential shapes used by scan diagnostics and eval artifact
# minimization. Keep this list single-sourced: persisted/report text must redact
# exactly the values the scanner calls high-confidence secrets.
SECRET_PATTERNS = [
    # AWS long-term (AKIA) and temporary/STS (ASIA) access key ids are both
    # 20-char credential material; the STS shape is what CI runners and assumed
    # roles leak most often.
    ("AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    # Legacy PATs/OAuth/app tokens (`gh[pousr]_...`) plus fine-grained PATs
    # (`github_pat_...`), which are now GitHub's default token shape and carry an
    # internal `_` separator between the id and secret halves.
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}\b")),
    # Google OAuth 2.0 client secrets carry the distinctive `GOCSPX-` prefix and
    # commonly leak inside MCP/OAuth env blocks alongside the `AIza` API key.
    ("Google OAuth client secret", re.compile(r"\bGOCSPX-[A-Za-z0-9_\-]{20,}\b")),
    # `xoxe` covers Slack Enterprise Grid tokens alongside bot/app/refresh/etc.
    ("Slack token", re.compile(r"\bxox[baprse]-[0-9A-Za-z-]{10,}\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    # LLM-provider API keys frequently pasted into MCP server `env` blocks and
    # agent settings. Each shape carries a distinctive prefix, so recall stays
    # high without the false positives of matching bare high-entropy strings.
    # OpenRouter (`sk-or-v1-…`) must have its own entry: the `-or-v1-` infix
    # breaks the contiguous run the OpenAI `sk-` pattern requires, so it would
    # otherwise escape both detection and redaction.
    ("OpenRouter API key", re.compile(r"\bsk-or-v1-[A-Za-z0-9]{20,}\b")),
    ("Groq API key", re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b")),
    ("xAI API key", re.compile(r"\bxai-[A-Za-z0-9]{20,}\b")),
    ("Perplexity API key", re.compile(r"\bpplx-[A-Za-z0-9]{20,}\b")),
    ("HuggingFace token", re.compile(r"\bhf_[A-Za-z]{20,}\b")),
    ("GitLab PAT", re.compile(r"\bglpat-[A-Za-z0-9\-_]{20,}\b")),
    ("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b")),
    ("PyPI token", re.compile(r"\bpypi-[A-Za-z0-9_\-]{16,}\b")),
    ("Stripe secret key", re.compile(r"\b[sr]k_live_[0-9A-Za-z]{16,}\b")),
    # Additional agent/MCP-ecosystem service credentials that leak in `.mcp.json`
    # env blocks and agent settings alongside the LLM-provider keys above. Each
    # carries a distinctive prefix (or fixed dotted shape), so recall stays high
    # without matching bare high-entropy strings.
    # Tavily is the web-search API most commonly wired into agents/MCP servers;
    # keys are `tvly-<random>` (dev keys add a `dev-` infix).
    ("Tavily API key", re.compile(r"\btvly-(?:dev-)?[A-Za-z0-9]{16,}\b")),
    # DigitalOcean personal/OAuth/refresh tokens (`dop_v1_`/`doo_v1_`/`dor_v1_`)
    # are 64 hex chars and leak from infra/deploy MCP servers.
    ("DigitalOcean token", re.compile(r"\bdo[opr]_v1_[a-f0-9]{64}\b")),
    # Doppler secret-manager tokens carry a fixed `dp.<type>.` prefix (personal,
    # service, CLI, service-account, SCIM, audit).
    ("Doppler token", re.compile(r"\bdp\.(?:pt|st|ct|sa|scim|audit)\.[A-Za-z0-9]{20,}\b")),
    # SendGrid API keys have the fixed `SG.<22>.<43>` base64url shape.
    ("SendGrid API key", re.compile(r"\bSG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}\b")),
    ("JSON Web Token", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    (
        "Generic hardcoded secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret(?:[_-]?key)?|access[_-]?key|client[_-]?secret|token|password|passwd|"
            r"auth[_-]?token|bearer)\b\s*[:=]\s*"
            r"(?:['\"][^'\"\s]{12,}['\"]|(?P<unquoted>[A-Za-z0-9+/_\-.]{16,}={0,2}))"
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
