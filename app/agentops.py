from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Dict, Any
import secrets

SEVERITIES = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


@dataclass
class Finding:
    severity: str
    category: str
    title: str
    detail: str
    recommendation: str
    owner: str
    status: str = "OPEN"


@dataclass
class AgentResult:
    agent: str
    role: str
    status: str
    summary: str
    findings: List[Finding]
    score: int
    duration_ms: int


def _result(agent, role, status, summary, findings, score, duration_ms):
    return AgentResult(agent, role, status, summary, findings, score, duration_ms)


def developer_agent():
    return _result("Developer", "Implementation", "READY",
                    "Architecture is implementable with isolated API, policy and UI layers.", [], 92, 184)


def security_agent():
    findings = [
        Finding("HIGH", "Authorization", "Authorization check missing on /api/projects/{id}",
                "Object access must be tenant-scoped; otherwise an authenticated user could request another tenant's object.",
                "Enforce ownership/tenant authorization before object retrieval and return a generic denial response.", "Security"),
        Finding("MEDIUM", "Supply Chain", "Dependency review required",
                "Production dependencies should be pinned and checked against a vulnerability policy.",
                "Pin supported versions and run dependency vulnerability/SBOM checks in CI.", "Security"),
    ]
    return _result("Security", "Security & Threat Modeling", "BLOCKED",
                    "Access control and supply-chain gates require remediation.", findings, 61, 241)


def qa_agent():
    findings = [
        Finding("MEDIUM", "Testing", "Add authorization regression test",
                "The critical access-control path needs a negative test covering another tenant's object ID.",
                "Add positive and negative two-tenant authorization tests to the regression suite.", "QA"),
        Finding("LOW", "Testing", "Add API contract coverage",
                "Contract tests would detect response-shape drift between backend and dashboard.",
                "Add schema validation for the public API responses.", "QA"),
    ]
    return _result("QA", "Verification & Regression", "REVIEW",
                    "Core behavior is testable; authorization and contract coverage should be expanded.", findings, 84, 198)


def data_agent():
    findings = [Finding("LOW", "Observability", "Add KPI persistence",
                        "Scores and findings are currently runtime-only in the demo.",
                        "Persist run summaries for trend analysis and management reporting.", "Data")]
    return _result("Data", "Analytics & Intelligence", "READY",
                    "The control center can track risk, agent scores, findings and release readiness.", findings, 90, 167)


def research_agent():
    return _result("Research", "Technical Research", "READY",
                    "The orchestration pattern supports specialist agents, tools, guardrails and human approval.", [], 88, 156)


def compliance_agent():
    findings = [Finding("MEDIUM", "Governance", "Define production approval policy",
                        "A production deployment needs an explicit policy for severity thresholds, ownership and evidence.",
                        "Document release gates and require evidence before approval.", "Governance")]
    return _result("Governance", "Policy & Compliance", "REVIEW",
                    "Governance controls exist conceptually but need a production policy definition.", findings, 82, 143)


def observability_agent():
    findings = [Finding("LOW", "Observability", "Connect persistent tracing",
                        "The demo records a local audit timeline but not distributed traces.",
                        "Connect structured traces, metrics and alerts for production agent runs.", "Platform")]
    return _result("Observability", "Tracing & Monitoring", "READY",
                    "Audit events are present; production telemetry can be added without changing the gate model.", findings, 87, 132)


def review_agent(results: List[AgentResult]):
    findings = [f for r in results for f in r.findings]
    critical = sum(f.severity == "CRITICAL" for f in findings)
    high = sum(f.severity == "HIGH" for f in findings)
    medium = sum(f.severity == "MEDIUM" for f in findings)
    if critical or high:
        status = "BLOCKED"
        score = max(0, 100 - critical * 25 - high * 15 - medium * 5)
        summary = f"Release blocked: {critical} CRITICAL, {high} HIGH and {medium} MEDIUM findings require action."
    elif medium:
        status = "CONDITIONAL"
        score = max(0, 100 - medium * 5)
        summary = f"Release is conditionally ready: {medium} MEDIUM findings require documented acceptance or remediation."
    else:
        status, score, summary = "APPROVED", 98, "All release gates satisfied."
    return _result("Review", "Release Gate & Human Approval", status, summary, [], score, 121)


def run_demo(project: str = "AgentOps Final Demo", runtime: str = "deterministic") -> Dict[str, Any]:
    results = [developer_agent(), security_agent(), qa_agent(), data_agent(), research_agent(), compliance_agent(), observability_agent()]
    review = review_agent(results)
    results.append(review)
    findings = [asdict(f) for r in results for f in r.findings]
    scores = [r.score for r in results]
    overall = round(sum(scores) / len(scores))
    counts = {s: sum(f["severity"] == s for f in findings) for s in SEVERITIES}
    blocked = review.status == "BLOCKED"
    now = datetime.now(timezone.utc).isoformat()
    run_id = f"demo-{secrets.token_hex(4)}"
    audit = [{"event": "RUN_STARTED", "agent": "Orchestrator", "status": "RUNNING"}]
    audit += [{"event": "AGENT_COMPLETED", "agent": r.agent, "status": r.status, "score": r.score, "duration_ms": r.duration_ms} for r in results[:-1]]
    audit += [{"event": "RELEASE_GATE", "agent": "Review", "status": review.status, "high": counts["HIGH"], "medium": counts["MEDIUM"]}]
    recommendations = list(dict.fromkeys(f["recommendation"] for f in findings))
    return {
        "project": project,
        "runtime": runtime,
        "run_id": run_id,
        "timestamp": now,
        "mode": "safe-demo",
        "architecture": "orchestrator + specialist agents + policy gate + human approval",
        "overall_score": overall,
        "release_status": review.status,
        "release_gate": {"passed": not blocked, "status": review.status, "counts": counts,
                         "thresholds": {"block_on": ["CRITICAL", "HIGH"], "conditional_on": ["MEDIUM"]}},
        "agents": [asdict(r) for r in results],
        "findings": findings,
        "recommendations": recommendations,
        "remediation_queue": [dict(f, id=f"F-{i:03d}") for i, f in enumerate(findings, 1)],
        "approval": {"allowed": not blocked, "decision": "PENDING", "requires_human": True},
        "audit_log": audit,
        "security": {"external_actions_enabled": False, "api_key_configured": False,
                      "sandboxed": True, "destructive_actions": "disabled"},
    }


def build_run_from_sdk_report(project: str, report: Dict[str, Any]) -> Dict[str, Any]:
    """Convert validated Agents SDK specialist evidence into the same control-plane shape.

    The LLM supplies evidence only. Release status, thresholds, remediation queue,
    and approval eligibility are calculated deterministically here.
    """
    results: List[AgentResult] = []
    for item in report.get("reports", []):
        findings = [Finding(**f) for f in item.get("findings", [])]
        results.append(_result(
            item.get("agent", "Unknown"),
            item.get("role", "Unknown"),
            item.get("status", "REVIEW"),
            item.get("summary", ""),
            findings,
            max(0, min(100, int(item.get("score", 0)))),
            0,
        ))

    expected = SPECIALIST_NAMES
    seen = {r.agent for r in results}
    for missing in [name for name in expected if name not in seen]:
        results.append(_result(missing, SPECIALIST_ROLES[missing], "FAILED",
                               "Specialist did not return a report.",
                               [Finding("HIGH", "Runtime", f"{missing} specialist report missing",
                                        "The live agent runtime did not return a validated specialist report.",
                                        "Retry the run or fall back to the deterministic runtime.", missing)],
                               0, 0))

    review = review_agent(results)
    results.append(review)
    findings = [asdict(f) for r in results for f in r.findings]
    scores = [r.score for r in results]
    overall = round(sum(scores) / len(scores)) if scores else 0
    counts = {s: sum(f["severity"] == s for f in findings) for s in SEVERITIES}
    blocked = review.status == "BLOCKED"
    now = datetime.now(timezone.utc).isoformat()
    run_id = f"agents-{secrets.token_hex(4)}"
    audit = [{"event": "RUN_STARTED", "agent": "AgentOps Manager", "status": "RUNNING"}]
    audit += [{"event": "AGENT_COMPLETED", "agent": r.agent, "status": r.status,
               "score": r.score, "duration_ms": r.duration_ms} for r in results[:-1]]
    audit += [{"event": "RELEASE_GATE", "agent": "Review", "status": review.status,
               "high": counts["HIGH"], "medium": counts["MEDIUM"]}]
    recommendations = list(dict.fromkeys(f["recommendation"] for f in findings))
    return {
        "project": project,
        "runtime": "agents_sdk",
        "run_id": run_id,
        "timestamp": now,
        "mode": "safe-agent-runtime",
        "architecture": "Agents SDK manager + specialist agents + deterministic policy gate + human approval",
        "overall_score": overall,
        "release_status": review.status,
        "release_gate": {"passed": not blocked, "status": review.status, "counts": counts,
                         "thresholds": {"block_on": ["CRITICAL", "HIGH"], "conditional_on": ["MEDIUM"]}},
        "agents": [asdict(r) for r in results],
        "findings": findings,
        "recommendations": recommendations,
        "remediation_queue": [dict(f, id=f"F-{i:03d}") for i, f in enumerate(findings, 1)],
        "approval": {"allowed": not blocked, "decision": "PENDING", "requires_human": True},
        "audit_log": audit,
        "security": {"external_actions_enabled": False, "api_key_configured": True,
                      "sandboxed": True, "destructive_actions": "disabled"},
        "agent_runtime_summary": report.get("summary", ""),
    }


SPECIALIST_NAMES = list(SPECIALIST_SPECS.keys()) if 'SPECIALIST_SPECS' in globals() else [
    "Developer", "Security", "QA", "Data", "Research", "Governance", "Observability"
]
SPECIALIST_ROLES = {
    "Developer": "Implementation",
    "Security": "Security & Threat Modeling",
    "QA": "Verification & Regression",
    "Data": "Analytics & Intelligence",
    "Research": "Technical Research",
    "Governance": "Policy & Compliance",
    "Observability": "Tracing & Monitoring",
}
