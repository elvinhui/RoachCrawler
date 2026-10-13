import json
import pytest
from pathlib import Path

from module_auto_healer.models import (
    CodeHunk,
    DiagnosisResult,
    FailureContext,
    VulnerabilityFix,
)
from module_auto_healer.validator import (
    contains_hardcoded_secrets,
    is_safe_target_path,
    validate_patch,
    validate_python_syntax,
)
from module_auto_healer.analyzer import (
    apply_code_hunks,
    apply_vulnerability_fixes,
    diagnose_failure,
    extract_error_snippet,
    extract_referenced_files,
)
from module_auto_healer.healer import (
    build_completion_slack_payload,
    build_heal_webhook_payload,
    execute_heal_workflow,
    main as healer_main,
    send_noc_notification,
)


def test_models_are_immutable():
    ctx = FailureContext(
        run_id="1001",
        workflow_name="🪳 RoachCrawler Auto Pipeline",
        log_excerpt="Traceback...",
        failed_files=(("scripts/coder_agent.py", "print('ok')"),),
    )
    with pytest.raises(Exception):
        ctx.run_id = "2002"  # type: ignore

    hunk = CodeHunk(target="a = 1", replacement="a = 2")
    with pytest.raises(Exception):
        hunk.target = "b = 1"  # type: ignore


def test_is_safe_target_path_roachcrawler(tmp_path: Path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)

    assert is_safe_target_path("scripts/coder_agent.py", str(tmp_path)) is True
    assert is_safe_target_path("scripts/serp_sniffer.py", str(tmp_path)) is True
    assert is_safe_target_path("requirements.txt", str(tmp_path)) is True

    # Disallowed paths
    assert is_safe_target_path("", str(tmp_path)) is False
    assert is_safe_target_path("../secrets.py", str(tmp_path)) is False
    assert is_safe_target_path(".github/workflows/pipeline.yml", str(tmp_path)) is False
    assert is_safe_target_path("smartinfralog-deployer_accessKeys.csv", str(tmp_path)) is False
    assert is_safe_target_path("/etc/passwd", str(tmp_path)) is False


def test_contains_hardcoded_secrets():
    assert contains_hardcoded_secrets("") is False
    assert contains_hardcoded_secrets('k = os.getenv("DEEPSEEK_API_KEY")') is False
    assert contains_hardcoded_secrets('k = "sk-proj-1234567890abcdef1234567890abcdef"') is True
    assert contains_hardcoded_secrets('k = "AKIAIOSFODNN7EXAMPLE"') is True


def test_validate_python_syntax_and_patch(tmp_path: Path):
    (tmp_path / "scripts").mkdir()
    orig = "\n".join([f"val_{i} = {i}" for i in range(20)]) + "\n"
    patched = orig.replace("val_3 = 3", "val_3 = 300")

    ok, msg = validate_patch("scripts/coder_agent.py", orig, patched, str(tmp_path))
    assert ok is True
    assert msg == "OK"

    assert validate_patch("evil.py", orig, patched, str(tmp_path))[0] is False
    assert validate_patch("scripts/coder_agent.py", orig, "  ", str(tmp_path))[0] is False
    assert validate_patch("scripts/coder_agent.py", orig, orig, str(tmp_path))[0] is False
    assert validate_patch("scripts/coder_agent.py", orig, "val_0 = 0\n", str(tmp_path))[0] is False
    assert validate_patch(
        "scripts/coder_agent.py",
        orig,
        orig + 'aws = "AKIA1234567890ABCDEF"\n',
        str(tmp_path),
    )[0] is False
    assert validate_patch(
        "scripts/coder_agent.py",
        orig,
        orig + "def broken(\n",
        str(tmp_path),
    )[0] is False


def test_extract_error_snippet_and_referenced_files(tmp_path: Path):
    assert extract_error_snippet("") == ""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    coder_py = scripts_dir / "coder_agent.py"
    coder_py.write_text("import httpx\nprint('ok')\n", encoding="utf-8")

    raw_log = (
        "2026-10-12T00:00:01.1234567Z [*] 正在拉起大模型双语算力...\n"
        "2026-10-12T00:00:02.1234567Z [-] 算力调度异常: DeepSeek timeout\n"
        "2026-10-12T00:00:03.1234567Z ##[error]Process completed with exit code 1.\n"
        "2026-10-12T00:00:04.1234567Z Post job cleanup.\n"
    )
    snippet = extract_error_snippet(raw_log)
    assert "算力调度异常" in snippet
    assert "Post job cleanup" not in snippet

    files = extract_referenced_files(snippet, str(tmp_path))
    assert len(files) == 1
    assert files[0][0] == "scripts/coder_agent.py"


def test_apply_vulnerability_fixes():
    req_txt = "pytrends\nrequests>=2.31.0\nhttpx\n"
    audit_payload = json.dumps({
        "dependencies": [
            {
                "name": "requests",
                "version": "2.31.0",
                "vulns": [{"id": "CVE-2024-35195", "fix_versions": ["2.32.3"]}],
            }
        ]
    })
    new_req, fixes = apply_vulnerability_fixes(req_txt, audit_payload)
    assert len(fixes) == 1
    assert "requests>=2.32.3" in new_req


def test_diagnose_and_execute_heal_workflow(tmp_path: Path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    target_py = scripts_dir / "serp_sniffer.py"
    orig_code = "\n".join([f"line_{i} = {i}" for i in range(15)]) + "\n"
    target_py.write_text(orig_code, encoding="utf-8")

    raw_log = (
        "Traceback (most recent call last):\n"
        '  File "scripts/serp_sniffer.py", line 5, in <module>\n'
        "ValueError: bad serp param\n"
    )

    outcome = execute_heal_workflow(
        run_id="777",
        workflow_name="🪳 RoachCrawler Auto Pipeline",
        raw_log=raw_log,
        project_root=str(tmp_path),
        api_key="dummy",
        llm_responder=lambda _s, _u: json.dumps({
            "category": "CODE_FIX",
            "root_cause": "Fixed line_5 in serp_sniffer.py",
            "target_file": "scripts/serp_sniffer.py",
            "patches": [{"target": "line_5 = 5", "replacement": "line_5 = 555"}],
        }),
    )
    assert outcome["action"] == "CODE_FIXED"
    assert "line_5 = 555" in target_py.read_text(encoding="utf-8")

    payload = build_heal_webhook_payload("🪳 RoachCrawler Auto Pipeline", outcome)
    assert "blocks" in payload
    assert send_noc_notification("", payload) is False


def test_cli_modes(tmp_path: Path, monkeypatch):
    gh_out = tmp_path / "gh_out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(gh_out))
    monkeypatch.setenv("NOC_WEBHOOK_URL", "")

    req_file = tmp_path / "requirements.txt"
    req_file.write_text("requests>=2.31.0\n", encoding="utf-8")
    audit_file = tmp_path / "audit.json"
    audit_file.write_text(
        json.dumps({
            "dependencies": [
                {
                    "name": "requests",
                    "version": "2.31.0",
                    "vulns": [{"id": "CVE-1", "fix_versions": ["2.32.3"]}],
                }
            ]
        }),
        encoding="utf-8",
    )

    rc = healer_main([
        "--mode", "audit-fix",
        "--requirements-file", str(req_file),
        "--audit-json-file", str(audit_file),
    ])
    assert rc == 0
    assert "requests>=2.32.3" in req_file.read_text(encoding="utf-8")

    log_file = tmp_path / "fail.log"
    log_file.write_text("Error: test", encoding="utf-8")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    rc2 = healer_main([
        "--mode", "heal-run",
        "--run-id", "888",
        "--workflow-name", "RoachCrawler",
        "--log-file", str(log_file),
        "--project-root", str(tmp_path),
    ])
    assert rc2 == 0
    assert "action=UNFIXABLE" in gh_out.read_text(encoding="utf-8")


def test_notify_complete_slack_integration(monkeypatch):
    sent_requests = []

    class DummyResp:
        def raise_for_status(self):
            return None

    def fake_post(url, json=None, timeout=10):
        sent_requests.append((url, json))
        return DummyResp()

    monkeypatch.setattr("module_auto_healer.healer.requests.post", fake_post)
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T00/B00/X00")

    payload = build_completion_slack_payload(
        workflow_name="🪳 RoachCrawler Auto Pipeline",
        target_file="scripts/serp_sniffer.py",
        branch_name="auto-fix/run-999",
        root_cause="Fixed MAX_DAILY_PUBLISH_LIMIT",
        run_url="https://github.com/elvinhui/RoachCrawler/actions/runs/999",
    )
    assert "text" in payload
    assert "blocks" in payload
    assert "scripts/serp_sniffer.py" in json.dumps(payload)

    rc = healer_main([
        "--mode", "notify-complete",
        "--workflow-name", "🪳 RoachCrawler Auto Pipeline",
        "--target-file", "scripts/serp_sniffer.py",
        "--branch-name", "auto-fix/run-999",
        "--root-cause", "Fixed MAX_DAILY_PUBLISH_LIMIT",
        "--run-url", "https://github.com/elvinhui/RoachCrawler/actions/runs/999",
    ])
    assert rc == 0
    assert len(sent_requests) == 1
    assert sent_requests[0][0] == "https://hooks.slack.com/services/T00/B00/X00"
    assert "auto-fix/run-999" in json.dumps(sent_requests[0][1])

