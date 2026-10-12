"""
Orchestrator and CLI entry point for RoachCrawler Autonomous Self-Healing Pipeline.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Optional
import requests

from module_auto_healer.analyzer import (
    apply_code_hunks,
    apply_vulnerability_fixes,
    diagnose_failure,
    extract_error_snippet,
    extract_referenced_files,
)
from module_auto_healer.models import FailureContext
from module_auto_healer.validator import validate_patch


def build_heal_webhook_payload(workflow_name: str, outcome: dict[str, Any]) -> dict[str, Any]:
    """Builds an immutable Slack Block Kit payload summarizing the self-healing action."""
    action = outcome.get("action", "UNFIXABLE")
    root_cause = outcome.get("root_cause", "No details available.")
    target_file = outcome.get("target_file")
    secret_name = outcome.get("secret_name")

    status_map = {
        "CODE_FIXED": "🛠️ *AI 已自动生成修复分支并验证通过*",
        "TRANSIENT_RERUN": "🔄 *检测到临时性网络/限流抖动，已触发自动重跑*",
        "CREDENTIALS_EXPIRED": "🔑 *检测到凭证/Key 过期，需人工更新 Secret*",
        "UNFIXABLE": "⚠️ *自动修复未命中安全规则，需人工排查*",
    }
    status_label = status_map.get(action, "ℹ️ *自愈引擎通知*")

    detail_lines = [f"*Workflow:* `{workflow_name}`", f"*Root Cause:* {root_cause}"]
    if target_file:
        detail_lines.append(f"*Patched File:* `{target_file}`")
    if secret_name:
        detail_lines.append(f"*Expired Secret:* `{secret_name}`")

    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🪳 RoachCrawler | Auto-Healer 自愈引擎",
                    "emoji": True,
                },
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": status_label}],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(detail_lines)},
            },
        ]
    }


def send_noc_notification(webhook_url: str, payload: dict[str, Any]) -> bool:
    """Sends a notification card to NOC_WEBHOOK_URL if configured."""
    if not webhook_url:
        return False
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as exc:
        print(f"Warning: Failed to send NOC notification: {exc}")
        return False


def execute_heal_workflow(
    run_id: str,
    workflow_name: str,
    raw_log: str,
    project_root: str,
    api_key: str,
    llm_responder: Optional[Callable[[str, str], str]] = None,
) -> dict[str, Any]:
    """
    Runs end-to-end diagnosis and validated patch application for a failed workflow run.
    Returns an immutable dictionary describing the action taken.
    """
    snippet = extract_error_snippet(raw_log)
    referenced_files = extract_referenced_files(snippet, project_root)

    context = FailureContext(
        run_id=run_id,
        workflow_name=workflow_name,
        log_excerpt=snippet,
        failed_files=referenced_files,
    )

    diagnosis = diagnose_failure(context, api_key=api_key, llm_responder=llm_responder)

    if diagnosis.category == "TRANSIENT":
        return {
            "action": "TRANSIENT_RERUN",
            "root_cause": diagnosis.root_cause,
            "target_file": None,
            "secret_name": None,
        }

    if diagnosis.category == "CREDENTIALS_EXPIRED":
        return {
            "action": "CREDENTIALS_EXPIRED",
            "root_cause": diagnosis.root_cause,
            "target_file": None,
            "secret_name": diagnosis.secret_name,
        }

    if diagnosis.category == "CODE_FIX" and diagnosis.target_file:
        target_rel = diagnosis.target_file.replace("\\", "/").lstrip("./")
        full_path = Path(project_root).resolve() / target_rel
        original_content = (
            full_path.read_text(encoding="utf-8") if full_path.is_file() else ""
        )

        candidate_content = diagnosis.patched_content or ""
        if diagnosis.patches and original_content:
            candidate_content = apply_code_hunks(original_content, diagnosis.patches)

        is_valid, reason = validate_patch(
            target_rel, original_content, candidate_content, project_root
        )
        if not is_valid:
            return {
                "action": "UNFIXABLE",
                "root_cause": f"{diagnosis.root_cause} (Patch rejected by guardrail: {reason})",
                "target_file": target_rel,
                "secret_name": None,
            }

        full_path.write_text(candidate_content, encoding="utf-8")
        return {
            "action": "CODE_FIXED",
            "root_cause": diagnosis.root_cause,
            "target_file": target_rel,
            "secret_name": None,
        }

    return {
        "action": "UNFIXABLE",
        "root_cause": diagnosis.root_cause,
        "target_file": None,
        "secret_name": None,
    }


def _write_github_output(outputs: dict[str, str]) -> None:
    """Writes key-value pairs to $GITHUB_OUTPUT when running inside GitHub Actions."""
    gh_out = os.getenv("GITHUB_OUTPUT")
    if not gh_out:
        return
    with open(gh_out, "a", encoding="utf-8") as f:
        for k, v in outputs.items():
            clean_val = str(v or "").replace("\n", " ").strip()
            f.write(f"{k}={clean_val}\n")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="RoachCrawler Auto-Healer CLI")
    parser.add_argument(
        "--mode",
        choices=["heal-run", "audit-fix"],
        required=True,
        help="Operation mode: heal a failed workflow run or apply pip-audit fixes.",
    )
    parser.add_argument("--run-id", default="", help="Failed GitHub Actions run ID")
    parser.add_argument("--workflow-name", default="Workflow", help="Failed workflow name")
    parser.add_argument("--log-file", default="", help="Path to downloaded failure log file")
    parser.add_argument("--audit-json-file", default="", help="Path to pip-audit JSON file")
    parser.add_argument("--requirements-file", default="", help="Path to requirements.txt")
    parser.add_argument("--project-root", default=".", help="Repository root path")
    args = parser.parse_args(argv)

    webhook_url = os.getenv("NOC_WEBHOOK_URL", "")

    if args.mode == "audit-fix":
        req_path = Path(args.requirements_file)
        audit_path = Path(args.audit_json_file)
        if not req_path.is_file() or not audit_path.is_file():
            print("No requirements or audit file found.")
            _write_github_output({"vuln_fixed": "false"})
            return 0

        orig_req = req_path.read_text(encoding="utf-8")
        audit_json = audit_path.read_text(encoding="utf-8")
        new_req, fixes = apply_vulnerability_fixes(
            orig_req, audit_json, str(req_path)
        )
        if fixes and new_req != orig_req:
            req_path.write_text(new_req, encoding="utf-8")
            summary = ", ".join(
                f"{fx.package_name} ({fx.current_version} -> {fx.fixed_version})"
                for fx in fixes
            )
            print(f"Upgraded vulnerable packages: {summary}")
            _write_github_output({"vuln_fixed": "true", "vuln_summary": summary})
        else:
            print("No fixable vulnerabilities detected.")
            _write_github_output({"vuln_fixed": "false"})
        return 0

    raw_log = ""
    if args.log_file and Path(args.log_file).is_file():
        raw_log = Path(args.log_file).read_text(encoding="utf-8", errors="replace")

    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
    outcome = execute_heal_workflow(
        run_id=args.run_id,
        workflow_name=args.workflow_name,
        raw_log=raw_log,
        project_root=args.project_root,
        api_key=api_key,
    )

    print(f"Auto-Healer Outcome: {json.dumps(outcome, ensure_ascii=False)}")
    _write_github_output({
        "action": outcome["action"],
        "target_file": outcome.get("target_file") or "",
        "root_cause": outcome.get("root_cause") or "",
    })

    if webhook_url:
        payload = build_heal_webhook_payload(args.workflow_name, outcome)
        send_noc_notification(webhook_url, payload)

    return 0


if __name__ == "__main__":
    sys.exit(main())
