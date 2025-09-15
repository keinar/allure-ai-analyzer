import re
import os
from typing import Dict, Any

_WHITESPACE_RE = re.compile(r"\s+")

def _flatten_whitespace(s: str) -> str:
    """Collapse any whitespace (including newlines) to a single space."""
    return _WHITESPACE_RE.sub(" ", s or "").strip()

class Fingerprinter:
    def __init__(self, **kwargs):
        self.specific_patterns = [
            (re.compile(r"waiting for selector `(.*?)` failed", re.IGNORECASE), r"Timeout for selector: \1"),
            (re.compile(r"Custom message:\s*Expected the status code to be (\d+), but found (\d+)", re.IGNORECASE | re.DOTALL), r"Assertion: Expected status code \1 but received \2"),
            (re.compile(r"Custom message:\s*(export didn't end with status SUCCEEDED, but ended with status IN_PROGRESS)", re.IGNORECASE | re.DOTALL), r"Assertion: \1"),
            (re.compile(r"Custom message:\s*(expected toggle icon to be not displayed)", re.IGNORECASE | re.DOTALL), r"Assertion: \1"),
            (re.compile(r"Custom message:\s*(checkbox is not checked:.*)", re.IGNORECASE | re.DOTALL), r"Assertion: Checkbox not checked"),
            (re.compile(r"URL: (.*)", re.IGNORECASE), r"Navigation error on URL: \1"),
            (re.compile(r"Missing test issue id for Xray report", re.IGNORECASE), r"Config error: Missing Xray issue ID"),
            (re.compile(r"NO_ENTITY_FOUND_ERROR", re.IGNORECASE), r"Backend error: NO_ENTITY_FOUND_ERROR"),
            (re.compile(r"Failed to load resource: (net::\w+)", re.IGNORECASE), r"Network error: \1"),
            # Shorten very long CSP message
            (re.compile(r"Refused to execute inline (?:event handler|script).*?Content Security Policy", re.IGNORECASE | re.DOTALL),
             "CSP Violation: Refused to execute inline script"),
        ]

        self.generic_patterns = [
            (re.compile(r"[a-f0-9]{8}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{4}-?[a-f0-9]{12}", re.I), "<UUID>"),
            (re.compile(r"\b\d{5,}\b"), "<LONG_NUM>"),
            (re.compile(r"status of (\d{3})"), r"status of <STATUS_CODE>"),
        ]

    MAX_TITLE_LEN = 160  # display limit only

    @staticmethod
    def _shorten(s: str, n: int = 160) -> str:
        s = s.strip()
        return (s[: n - 1] + "…") if len(s) > n else s

    @staticmethod
    def _first_non_empty_line(s: str) -> str:
        for ln in (s or "").splitlines():
            if ln.strip():
                return _WHITESPACE_RE.sub(" ", ln.strip())
        return ""

    def _create_message_key(self, failure: Dict) -> str:
        """Build a concise, meaningful 'What' string for the fingerprint/title."""
        raw = failure.get("message") or ""

        # Flatten only for "Custom message:", otherwise take first non-empty line
        if re.match(r"^\s*Custom message\s*:", raw, re.IGNORECASE):
            base = _flatten_whitespace(raw)
        else:
            base = self._first_non_empty_line(raw)

        if not base:
            return f"(No message found in: {failure.get('name', 'Unknown test')})"

        # Specific shortening on the matched segment only
        for pattern, replacement in self.specific_patterns:
            m = pattern.search(base)
            if m:
                short = pattern.sub(replacement, m.group(0))
                return self._shorten(short)

        # Generic fallback
        key = base

        if key.lower().startswith("unhandled error") or not key:
            return self._shorten(f"Unhandled Error in Test: {failure.get('name', 'Unknown test')}")

        for pattern, replacement in self.generic_patterns:
            key = pattern.sub(replacement, key)

        return self._shorten(key)

    def _get_code_location(self, trace: str) -> str:
        if not trace:
            return "(No stack trace)"
        match = re.search(r'at .*?((?:[/\\A-Za-z0-9_-]+\.)+spec\.(?:ts|js):\d+:\d+)', trace)
        if match:
            return os.path.basename(match.group(1))
        return "(No test file location in trace)"

    def create_fingerprint(self, failure: Dict[str, Any]) -> str:
        message_key = self._create_message_key(failure)
        code_location = self._get_code_location(failure.get("trace", ""))
        return f"{message_key}|{code_location}"