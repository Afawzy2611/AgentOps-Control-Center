"""Severity normalization for release-gate fail-closed behavior."""

SEVERITIES = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
VALID_SEVERITIES = frozenset(SEVERITIES)


def normalize_severity(severity: str | None) -> str:
    """Normalize severity labels for gate evaluation.

    Unknown or empty values are treated as CRITICAL so they fail closed
    (block release) rather than bypassing the gate.
    """
    normalized = (severity or "").upper().strip()
    if normalized not in VALID_SEVERITIES:
        return "CRITICAL"
    return normalized
