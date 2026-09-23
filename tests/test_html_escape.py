"""Unit tests for UI HTML escaping (XSS defensive)."""

from __future__ import annotations

import re
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "app" / "static" / "index.html"

# Mirror of the browser esc() map used in app/static/index.html.
_ESC_MAP = {
    "&": "&",
    "<": "<",
    ">": ">",
    '"': """,
    "'": "&#39;",
}


def esc(s: str) -> str:
    """Python mirror of the control-center UI esc() helper."""
    return re.sub(r'[&<>"\']', lambda m: _ESC_MAP[m.group(0)], str(s))


def test_index_html_esc_uses_html_entities_not_identity():
    source = INDEX.read_text(encoding="utf-8")
    match = re.search(r"function esc\(s\)\{.*?\}\n", source, re.DOTALL)
    if not match:
        match = re.search(r"function esc\(s\)\{[^\n]+\}", source)
    assert match, "esc() function missing from index.html"
    body = match.group(0)
    assert "&" in body and "<" in body and ">" in body and """ in body
    # Identity mapping bug regression: must not map &→& / <→< literally as values.
    assert "{'&':'&'," not in body
    assert "{'&':'&'" in body


def test_esc_escapes_xss_ish_finding_title():
    title = '<script>alert("xss")</script>'
    out = esc(title)
    assert "<script>" not in out
    assert "<script>" in out
    assert ""xss"" in out
    assert esc("a & b < c > d") == "a & b < c > d"
    assert esc("it's") == "it&#39;s"
