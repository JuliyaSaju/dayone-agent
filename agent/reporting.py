"""Turns a Report into readable text and a JSON file."""
import json
from pathlib import Path


def render(report) -> str:
    lines = [f"\n=== TASK {report.task_id}: {report.status} ===", f"Request: {report.request}"]
    if report.intent:
        i = report.intent
        lines.append(f"Understood as: {i.action} {i.first_name} {i.last_name}, role={i.role}, extra={i.extra_access}")
    if report.notes:
        lines.append("Notes:")
        lines += [f"  - {n}" for n in report.notes]
    lines.append("Actions taken (audit log):")
    for a in report.actions:
        res = a["result"] or {}
        outcome = res.get("result") or res.get("error") or res.get("detail") or ""
        lines.append(f"  [{a['status']:>8}] {a['tool']} {json.dumps(a['args'])} -> {outcome}")
    if report.checks:
        lines.append("Independent verification:")
        for c in report.checks:
            mark = "PASS" if c.passed else "FAIL"
            lines.append(f"  [{mark}] {c.name}" + (f" ({c.detail})" if c.detail else ""))
    if report.agent_summary:
        lines.append(f"Agent's own summary (NOT used for the status): {report.agent_summary}")
    lines.append(f"Time: {report.seconds}s")
    return "\n".join(lines)


def save(report, folder="reports") -> str:
    Path(folder).mkdir(exist_ok=True)
    path = Path(folder) / f"task_{report.task_id}.json"
    path.write_text(json.dumps(report.model_dump(), indent=2))
    return str(path)
