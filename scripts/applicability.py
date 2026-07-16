#!/usr/bin/env python3
"""Bounded structured applicability for recognized AI instruction formats.

This is intentionally NOT a YAML parser. It accepts only the documented
metadata controls needed by Claude ``.claude/rules/**/*.md``, Cursor ``.mdc``,
and Copilot/VS Code ``.instructions.md`` files. Unsupported YAML fails closed
for conflict analysis, while callers can still inventory and security-scan the
original file.
"""

import re
from pathlib import PurePosixPath

MODES = {"always", "path", "conditional", "manual", "ignored", "invalid"}
SUPPORTED_FORMATS = {
    "claude-rules",
    "cursor-mdc",
    "cursor-ignored-md",
    "copilot-instructions",
}
_CONTROL_FIELDS = {
    "claude-rules": {"paths"},
    "cursor-mdc": {"alwaysApply", "description", "globs"},
    "copilot-instructions": {"applyTo", "description", "name"},
}
_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_GLOB_CACHE = {}


class FrontmatterError(ValueError):
    """A safe metadata-only structured-rule parse failure."""


def _frontmatter_bounds(text, truncated=False):
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].lstrip("\ufeff").strip() != "---":
        return lines, None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines, index
    reason = (
        "frontmatter is truncated by the semantic byte budget"
        if truncated
        else "frontmatter is missing its closing delimiter"
    )
    raise FrontmatterError(reason)


def _decode_scalar(raw, field):
    value = raw.strip()
    if not value:
        return ""
    if value[:1] in {"'", '"'}:
        quote = value[0]
        if len(value) < 2 or value[-1] != quote:
            raise FrontmatterError(f"field `{field}` has an unterminated quote")
        body = value[1:-1]
        if quote == '"':
            # The supported subset needs common quoted glob strings, not full
            # YAML escaping. Reject unknown escapes rather than guessing.
            if re.search(r"\\(?![\\\"\[\]])", body):
                raise FrontmatterError(f"field `{field}` uses an unsupported escape")
            body = body.replace(r"\\", "\\").replace(r"\"", '"')
        return body
    if value.startswith(("[", "{", "|", ">", "&", "*", "!", "@", "`")):
        raise FrontmatterError(f"field `{field}` uses unsupported YAML syntax")
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value


def _decode_inline_sequence(raw, field):
    value = raw.strip()
    if not (value.startswith("[") and value.endswith("]")):
        raise FrontmatterError(f"field `{field}` must use a block or inline sequence")
    inner = value[1:-1].strip()
    if not inner:
        return []
    items = []
    for raw_item in _split_inline_sequence(inner, field):
        item = raw_item.strip()
        if item[:1] not in {"'", '"'}:
            raise FrontmatterError(f"field `{field}` inline items must be quoted strings")
        decoded = _decode_scalar(item, field)
        if not decoded:
            raise FrontmatterError(f"field `{field}` contains an empty item")
        items.append(decoded)
    return items


def _split_inline_sequence(value, field):
    """Split a bounded inline YAML string sequence without parsing YAML."""
    parts = []
    start = 0
    quote = None
    escaped = False
    brace_depth = 0
    class_depth = 0
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if quote and char == "\\":
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            continue
        if quote is not None:
            continue
        if char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth -= 1
            if brace_depth < 0:
                raise FrontmatterError(f"field `{field}` has an unmatched closing brace")
        elif char == "[":
            class_depth += 1
        elif char == "]":
            class_depth -= 1
            if class_depth < 0:
                raise FrontmatterError(f"field `{field}` has an unmatched closing bracket")
        elif char == "," and brace_depth == 0 and class_depth == 0:
            parts.append(value[start:index])
            start = index + 1
    if quote is not None:
        raise FrontmatterError(f"field `{field}` has an unterminated quote")
    if brace_depth or class_depth:
        raise FrontmatterError(f"field `{field}` has unbalanced syntax")
    parts.append(value[start:])
    return parts


def parse_frontmatter(text, format_kind, truncated=False):
    """Return ``(metadata, line-preserving body, first_body_line)``.

    Missing frontmatter is represented by ``metadata=None``. If an opening
    delimiter is present, every line in the block is blanked in the body so
    signal evidence retains the source file's original line numbers.
    """
    lines, closing = _frontmatter_bounds(text, truncated=truncated)
    if closing is None:
        return None, text, 1

    controls = _CONTROL_FIELDS.get(format_kind, set())
    metadata = {}
    for offset, line in enumerate(lines[1:closing], 2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            raise FrontmatterError(f"frontmatter line {offset} is not a scalar field")
        key, raw = line.split(":", 1)
        key = key.strip()
        if not _KEY_RE.fullmatch(key):
            raise FrontmatterError(f"frontmatter line {offset} has an invalid field name")
        if key not in controls:
            raise FrontmatterError(f"field `{key}` is unsupported")
        if key in metadata:
            raise FrontmatterError(f"field `{key}` is duplicated")
        metadata[key] = _decode_scalar(raw, key)

    body = list(lines)
    for index in range(closing + 1):
        ending = "\n" if body[index].endswith("\n") else ""
        body[index] = ending
    return metadata, "".join(body), closing + 2


def parse_claude_frontmatter(text, truncated=False):
    """Parse Claude's bounded ``paths``-only frontmatter subset."""
    lines, closing = _frontmatter_bounds(text, truncated=truncated)
    if closing is None:
        return None, text, 1

    paths = None
    index = 1
    while index < closing:
        line = lines[index]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        if ":" not in line:
            raise FrontmatterError(f"frontmatter line {index + 1} is not a supported field")
        key, raw = line.split(":", 1)
        key = key.strip()
        if key != "paths":
            raise FrontmatterError(f"field `{key}` is unsupported")
        if paths is not None:
            raise FrontmatterError("field `paths` is duplicated")
        if raw.strip():
            paths = _decode_inline_sequence(raw, "paths")
            index += 1
            continue
        paths = []
        index += 1
        while index < closing:
            item_line = lines[index]
            item = item_line.strip()
            if not item or item.startswith("#"):
                index += 1
                continue
            if not item.startswith("-"):
                break
            value = _decode_scalar(item[1:].strip(), "paths")
            if not value:
                raise FrontmatterError("field `paths` contains an empty item")
            paths.append(value)
            index += 1
        continue

    body = list(lines)
    for body_index in range(closing + 1):
        ending = "\n" if body[body_index].endswith("\n") else ""
        body[body_index] = ending
    return ({"paths": paths} if paths is not None else {}), "".join(body), closing + 2


def _boolean(value, field, default=None):
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise FrontmatterError(f"field `{field}` must be true or false")


def _validate_character_classes(value):
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\":
            if index + 1 >= len(value) or value[index + 1] not in "[]\\":
                raise FrontmatterError("glob pattern uses an unsupported escape")
            index += 2
            continue
        if char == "]":
            raise FrontmatterError("glob pattern has an unmatched closing class")
        if char != "[":
            index += 1
            continue
        closing = value.find("]", index + 1)
        if closing < 0:
            raise FrontmatterError("glob pattern has an unmatched opening class")
        content = value[index + 1 : closing]
        if not content or "/" in content or "\\" in content or any(char in content for char in "{}"):
            raise FrontmatterError("glob character class is empty or invalid")
        _character_class_regex(content)
        index = closing + 1


def _character_class_regex(content):
    negate = content[:1] in {"!", "^"}
    if negate:
        content = content[1:]
    if not content:
        raise FrontmatterError("glob character class is empty or invalid")
    class_parts = []
    for class_index, class_char in enumerate(content):
        if class_char == "-" and 0 < class_index < len(content) - 1:
            class_parts.append("-")
        else:
            class_parts.append(re.escape(class_char))
    source = "[" + ("^" if negate else "") + "".join(class_parts) + "]"
    try:
        re.compile(source)
    except re.error as exc:
        raise FrontmatterError("glob character class is invalid") from exc
    return source


def _validate_glob(pattern, character_classes=False):
    value = pattern.strip()
    if not character_classes:
        value = value.replace("\\", "/")
    if not value:
        raise FrontmatterError("glob patterns must be non-empty")
    if "\x00" in value or "\n" in value or "\r" in value:
        raise FrontmatterError("glob patterns must stay on one line")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:/", value) or value.startswith("~"):
        raise FrontmatterError("glob patterns must be contained workspace-relative paths")
    if value.startswith(("./", "/")):
        raise FrontmatterError("glob patterns must be normalized workspace-relative paths")
    if character_classes:
        _validate_character_classes(value)
    elif any(ch in value for ch in "[]"):
        raise FrontmatterError("glob patterns use unsupported character-class syntax")
    return value


def _split_outside_braces(value):
    parts = []
    start = 0
    depth = 0
    for index, char in enumerate(value):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                raise FrontmatterError("glob pattern has an unmatched closing brace")
        elif char == "," and depth == 0:
            parts.append(value[start:index])
            start = index + 1
    if depth:
        raise FrontmatterError("glob pattern has an unmatched opening brace")
    parts.append(value[start:])
    return parts


def _matching_brace(value, opening):
    depth = 0
    for index in range(opening, len(value)):
        if value[index] == "{":
            depth += 1
        elif value[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise FrontmatterError("glob pattern has an unmatched opening brace")


def _expand_braces(pattern, limit=64):
    """Expand bounded comma alternatives, including nested alternatives."""
    opening = pattern.find("{")
    if opening < 0:
        if "}" in pattern:
            raise FrontmatterError("glob pattern has an unmatched closing brace")
        return [pattern]
    closing = _matching_brace(pattern, opening)
    alternatives = _split_outside_braces(pattern[opening + 1 : closing])
    if len(alternatives) < 2 or any(not item for item in alternatives):
        raise FrontmatterError("glob brace expansion needs two or more non-empty alternatives")
    expanded = []
    for alternative in alternatives:
        candidate = pattern[:opening] + alternative + pattern[closing + 1 :]
        expanded.extend(_expand_braces(candidate, limit=limit))
        if len(expanded) > limit:
            raise FrontmatterError(f"glob brace expansion exceeds the {limit}-pattern limit")
    return expanded


def _patterns(value, field):
    if value is None:
        return []
    patterns = []
    for item in _split_outside_braces(str(value)):
        validated = _validate_glob(item)
        patterns.extend(_validate_glob(value) for value in _expand_braces(validated))
    if not patterns:
        raise FrontmatterError(f"field `{field}` needs a glob pattern")
    return list(dict.fromkeys(patterns))


def _claude_patterns(values):
    patterns = []
    for value in values:
        validated = _validate_glob(value, character_classes=True)
        patterns.extend(_validate_glob(expanded, character_classes=True) for expanded in _expand_braces(validated))
    if not patterns:
        raise FrontmatterError("field `paths` needs a glob pattern")
    return list(dict.fromkeys(patterns))


def classify(text, format_kind, path, truncated=False):
    """Return normalized applicability plus a line-preserving signal body."""
    del path  # File paths are report metadata; parsing is content/format-only.
    if format_kind not in SUPPORTED_FORMATS:
        return {
            "mode": "invalid",
            "format": str(format_kind),
            "patterns": [],
            "reason": "registry selected an unsupported applicability format",
            "line": 1,
            "signal_text": "",
        }
    if format_kind == "cursor-ignored-md":
        return {
            "mode": "ignored",
            "format": format_kind,
            "patterns": [],
            "reason": "Cursor project rules require the .mdc extension",
            "line": 1,
            "signal_text": "",
        }
    try:
        parser = parse_claude_frontmatter if format_kind == "claude-rules" else parse_frontmatter
        if format_kind == "claude-rules":
            metadata, body, _body_line = parser(
                text,
                truncated=truncated,
            )
        else:
            metadata, body, _body_line = parser(
                text,
                format_kind,
                truncated=truncated,
            )
        if format_kind == "claude-rules":
            if metadata is None or "paths" not in metadata:
                mode = "always"
                globs = []
            else:
                globs = _claude_patterns(metadata.get("paths", []))
                mode = "path"
        elif format_kind == "cursor-mdc":
            if metadata is None:
                raise FrontmatterError("Cursor .mdc rules require a frontmatter header")
            always = _boolean(metadata.get("alwaysApply"), "alwaysApply", False)
            description = metadata.get("description", "").strip()
            if always:
                mode = "always"
                globs = []
            else:
                globs = _patterns(metadata.get("globs"), "globs")
                if globs:
                    mode = "path"
                elif description:
                    mode = "conditional"
                else:
                    mode = "manual"
        elif format_kind == "copilot-instructions":
            if metadata is None:
                metadata = {}
                body = text
            globs = _patterns(metadata.get("applyTo"), "applyTo")
            description = metadata.get("description", "").strip()
            if globs:
                mode = "path"
            elif description:
                mode = "conditional"
            else:
                mode = "manual"
        return {
            "mode": mode,
            "format": format_kind,
            "patterns": globs,
            "line": 1,
            "signal_text": body,
        }
    except FrontmatterError as exc:
        return {
            "mode": "invalid",
            "format": format_kind,
            "patterns": [],
            "reason": str(exc),
            "line": 1,
            "signal_text": "",
        }


def _compile_glob(pattern):
    compiled = _GLOB_CACHE.get(pattern)
    if compiled is not None:
        return compiled
    parts = ["^"]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\" and index + 1 < len(pattern):
            parts.append(re.escape(pattern[index + 1]))
            index += 2
            continue
        if char == "[":
            closing = pattern.find("]", index + 1)
            if closing > index + 1:
                content = pattern[index + 1 : closing]
                parts.append(_character_class_regex(content))
                index = closing + 1
                continue
        if char == "*" and index + 1 < len(pattern) and pattern[index + 1] == "*":
            index += 2
            if index < len(pattern) and pattern[index] == "/":
                parts.append("(?:.*/)?")
                index += 1
            else:
                parts.append(".*")
            continue
        if char == "*":
            parts.append("[^/]*")
        elif char == "?":
            parts.append("[^/]")
        else:
            parts.append(re.escape(char))
        index += 1
    parts.append("$")
    compiled = re.compile("".join(parts))
    _GLOB_CACHE[pattern] = compiled
    return compiled


def matches(patterns, target):
    target = str(target).replace("\\", "/")
    if target.startswith("./"):
        target = target[2:]
    return any(_compile_glob(pattern).fullmatch(target) for pattern in patterns)
