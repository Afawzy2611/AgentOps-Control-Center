"""Unit tests for UI HTML escaping (XSS defensive)."""

from __future__ import annotations

import re
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "app" / "static" / "index.html"

AMP = "&" + "amp;"
LT = "&" + "lt;"
GT = "&" + "gt;"
QUOT = "&" + "quot;"
APOS = "&#39;"

_ESC_MAP = {"&": AMP, "<": LT, ">": GT, '"': QUOT, "'": APOS}


def esc(s: str) -> str:
    """Python mirror of the control-center UI esc() helper."""
    return re.sub(r'[&<>"\']', lambda m: _ESC_MAP[m.group(0)], str(s))


def test_index_html_esc_uses_x26_entity_escapes_not_identity():
    source = INDEX.read_text(encoding="utf-8")
    match = re.search(r"function esc\(s\)\{[^\n]+\}", source)
    assert match, "esc() function missing from index.html"
    body = match.group(0)
    assert r"\x26amp;" in body
    assert r"\x26lt;" in body
    assert r"\x26gt;" in body
    assert r"\x26quot;" in body
    assert "{'&':'&'," not in body


def test_esc_escapes_xss_ish_finding_title():
    title = '<script>alert("xss")</script>'
    out = esc(title)
    assert "<script>" not in out
    assert LT + "script" + GT in out
    assert QUOT + "xss" + QUOT in out
    assert esc("a & b < c > d") == f"a {AMP} b {LT} c {GT} d"
    assert esc("it's") == "it" + APOS + "s"
