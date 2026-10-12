"""
Log analysis, LLM root-cause diagnosis, and pip-audit vulnerability patching for RoachCrawler.
"""
import json
import re
from pathlib import Path
from typing import Callable, Optional

from module_auto_healer.models import (
    CodeHunk,
    DiagnosisResult,
    FailureContext,
    VulnerabilityFix,
)
from module_auto_healer.validator import is_safe_target_path

FILE_REF_PATTERN = re.compile(
    r'(?:File\s+"|in\s+|python\s+)([a-zA-Z0-9_./\\:-]+\.py)'
)

GH_LOG_PREFIX_PATTERN = re.compile(
    r"^.*?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\s?"
)


def _strip_gh_prefixes(text: str) -> str:
    """Removes GitHub Actions runner timestamps and job/step prefixes from log lines."""
    cleaned = [GH_LOG_PREFIX_PATTERN.sub("", line) for line in text.splitlines()]
    return "\n".join(cleaned)


def extract_error_snippet(raw_log: str, max_chars: int = 4000) -> str:
    """
    Extracts the most relevant error/traceback window from a GitHub Actions log,
    stripping runner timestamps and cutting off post-failure artifact/cleanup noise.
    """
    if not raw_log:
        return ""

    cleaned_log = _strip_gh_prefixes(raw_log)

    err_marker = "##[error]Process completed with exit code"
    err_idx = cleaned_log.find(err_marker)
    if err_idx != -1:
        line_end = cleaned_log.find("\n", err_idx)
        relevant_log = cleaned_log[: line_end if line_end != -1 else len(cleaned_log)]
    else:
        relevant_log = cleaned_log

    tb_idx = relevant_log.rfind("Traceback (most recent call last):")
    if tb_idx != -1:
        return relevant_log[tb_idx:][:max_chars]

    if err_idx != -1:
        lines_before = relevant_log.splitlines()[-65:]
        return "\n".join(lines_before)[-max_chars:]

    lines = [
        line for line in relevant_log.splitlines()
        if any(k in line.lower() for k in ("error", "exception", "fatal", "failed", "traceback", "异常", "坠毁", "错误"))
    ]
    if lines:
        return "\n".join(lines[-40:])[-max_chars:]

    return relevant_log[-max_chars:]


def extract_referenced_files(
    error_snippet: str,
    project_root: str,
) -> tuple[tuple[str, str], ...]:
    """
    Finds allowed RoachCrawler Python files (`scripts/*.py`) referenced in the traceback
    or matching logged failure messages, returning an immutable tuple of (relative_path, file_content).
    """
    matches = FILE_REF_PATTERN.findall(error_snippet)
    seen: set[str] = set()
    results: list[tuple[str, str]] = []
    root_path = Path(project_root).resolve()

    for match in matches:
        normalized = match.replace("\\", "/").lstrip("./")
        parts = normalized.split("/")
        rel_tail = "/".join(parts[-2:]) if len(parts) >= 2 else normalized
        basename = parts[-1]
        candidates = [
            normalized,
            rel_tail,
            f"scripts/{basename}",
        ]
        for candidate in candidates:
            if candidate in seen:
                continue
            if is_safe_target_path(candidate, project_root):
                full_path = root_path / candidate
                if full_path.is_file():
                    seen.add(candidate)
                    results.append((candidate, full_path.read_text(encoding="utf-8")))
                    break

    if not results:
        snippet_lower = error_snippet.lower()
        keyword_to_file = (
            (("算力调度", "双语", "lang_separator", "coder_agent"), "scripts/coder_agent.py"),
            (("嗅探", "探针", "serp", "target_data.txt"), "scripts/serp_sniffer.py"),
            (("quality gate", "quarantine", "thin content"), "scripts/quality_gate.py"),
            (("auto-fixer", "auto_fixer"), "scripts/auto_fixer.py"),
            (("post cleanup", "post_cleanup"), "scripts/post_cleanup.py"),
            (("s3", "upload_to_s3"), "scripts/upload_to_s3.py"),
            (("trend crawler", "trend_crawler"), "scripts/trend_crawler.py"),
        )
        for keywords, rel_candidate in keyword_to_file:
            if any(kw in snippet_lower for kw in keywords):
                if is_safe_target_path(rel_candidate, project_root):
                    full_path = root_path / rel_candidate
                    if full_path.is_file() and rel_candidate not in seen:
                        seen.add(rel_candidate)
                        results.append((rel_candidate, full_path.read_text(encoding="utf-8")))

    return tuple(results)


def apply_code_hunks(original_content: str, hunks: tuple[CodeHunk, ...]) -> str:
    """
    Immutably applies a sequence of search-and-replace hunks to `original_content`.
    Returns the new content string.
    """
    updated = original_content
    for hunk in hunks:
        if hunk.target and hunk.target in updated:
            updated = updated.replace(hunk.target, hunk.replacement, 1)
    return updated


def _default_llm_responder(
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
) -> str:
    """Calls DeepSeek API using httpx (native to RoachCrawler) and returns raw JSON text."""
    import httpx

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 4096,
        "temperature": 0.1,
    }
    resp = httpx.post(f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=payload, timeout=90)
    resp.raise_for_status()
    return (resp.json()["choices"][0]["message"]["content"] or "{}").strip()


def diagnose_failure(
    context: FailureContext,
    api_key: str,
    llm_responder: Optional[Callable[[str, str], str]] = None,
) -> DiagnosisResult:
    """
    Diagnoses a workflow failure using LLM and returns an immutable DiagnosisResult.
    """
    if not api_key and llm_responder is None:
        return DiagnosisResult(
            category="UNFIXABLE",
            root_cause="Missing LLM API key for autonomous diagnosis.",
        )

    system_prompt = (
        "You are an autonomous DevSecOps Self-Healing Agent for RoachCrawler.\n"
        "Analyze the GitHub Actions failure log and referenced source files.\n"
        "Output ONLY a valid JSON object with these keys:\n"
        '- "category": One of ["TRANSIENT", "CODE_FIX", "CREDENTIALS_EXPIRED", "UNFIXABLE"]\n'
        '- "root_cause": Concise 1-2 sentence explanation of why the workflow failed.\n'
        '- "target_file": Relative path (e.g. "scripts/coder_agent.py") if category is "CODE_FIX", else null.\n'
        '- "patches": A list of {"target": "<exact lines to find>", "replacement": "<new lines>"} objects '
        'for surgical code fixes when category is "CODE_FIX". Always prefer "patches" over regenerating large files.\n'
        '- "patched_content": Optional full replacement file content ONLY if the file is very short (<100 lines), else null.\n'
        '- "secret_name": Name of the expired GitHub Secret (e.g. "SERP_API_KEY", "DEEPSEEK_API_KEY", "AWS_ACCESS_KEY_ID") '
        'if category is "CREDENTIALS_EXPIRED", else null.\n'
        "Rules:\n"
        "1. Never hardcode secrets or tokens.\n"
        "2. In 'patches', 'target' MUST be an exact, verbatim substring from the source file.\n"
        "3. Use category 'CODE_FIX' if a logic bug, parsing error, or unhandled exception caused the failure."
    )

    files_section = "\n\n".join(
        f"--- FILE: {rel_path} ---\n{content}"
        for rel_path, content in context.failed_files
    )
    user_prompt = (
        f"Workflow: {context.workflow_name} (Run ID: {context.run_id})\n\n"
        f"=== ERROR LOG EXCERPT ===\n{context.log_excerpt}\n\n"
        f"=== REFERENCED SOURCE FILES ===\n{files_section or 'No local files referenced in traceback.'}"
    )

    try:
        raw_response = (
            llm_responder(system_prompt, user_prompt)
            if llm_responder is not None
            else _default_llm_responder(system_prompt, user_prompt, api_key)
        )
        parsed = json.loads(raw_response)
        category = str(parsed.get("category", "UNFIXABLE")).upper()
        if category not in {"TRANSIENT", "CODE_FIX", "CREDENTIALS_EXPIRED", "UNFIXABLE"}:
            category = "UNFIXABLE"

        raw_patches = parsed.get("patches") or []
        hunks = tuple(
            CodeHunk(
                target=str(item.get("target", "")),
                replacement=str(item.get("replacement", "")),
            )
            for item in raw_patches
            if isinstance(item, dict) and item.get("target")
        )

        return DiagnosisResult(
            category=category,
            root_cause=str(parsed.get("root_cause", "Unknown failure")),
            target_file=parsed.get("target_file"),
            patched_content=parsed.get("patched_content"),
            patches=hunks,
            secret_name=parsed.get("secret_name"),
        )
    except Exception as exc:
        return DiagnosisResult(
            category="UNFIXABLE",
            root_cause=f"Autonomous diagnosis failed: {exc}",
        )


def _pick_highest_version(versions: list[str]) -> str:
    """Picks the highest semantic version string from a list of fix_versions."""
    def _version_key(v: str) -> tuple[int, ...]:
        nums = re.findall(r"\d+", v)
        return tuple(int(n) for n in nums)

    return sorted(versions, key=_version_key)[-1]


def apply_vulnerability_fixes(
    req_content: str,
    audit_json: str,
    requirements_file: str = "",
) -> tuple[str, tuple[VulnerabilityFix, ...]]:
    """
    Parses `pip-audit --format=json` output and returns a new requirements.txt
    content string with vulnerable packages upgraded to their fixed versions,
    along with an immutable tuple of VulnerabilityFix records.
    """
    try:
        data = json.loads(audit_json)
    except Exception:
        return req_content, ()

    dependencies = data.get("dependencies", []) if isinstance(data, dict) else []
    upgrade_map: dict[str, VulnerabilityFix] = {}

    for dep in dependencies:
        pkg_name = str(dep.get("name", "")).strip()
        current_ver = str(dep.get("version", "")).strip()
        vulns = dep.get("vulns") or []
        all_fix_versions: list[str] = []
        for vuln in vulns:
            all_fix_versions.extend(vuln.get("fix_versions") or [])
        if pkg_name and all_fix_versions:
            best_fix = _pick_highest_version(all_fix_versions)
            upgrade_map[pkg_name.lower()] = VulnerabilityFix(
                package_name=pkg_name,
                current_version=current_ver,
                fixed_version=best_fix,
                requirements_file=requirements_file,
            )

    if not upgrade_map:
        return req_content, ()

    applied_fixes: list[VulnerabilityFix] = []
    new_lines: list[str] = []

    for line in req_content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue

        match = re.match(r"^([a-zA-Z0-9_.-]+)\s*([><=~!]+.*)?$", stripped)
        if not match:
            new_lines.append(line)
            continue

        pkg_raw = match.group(1)
        pkg_norm = pkg_raw.lower().replace("_", "-")
        fix_obj = upgrade_map.get(pkg_norm) or upgrade_map.get(pkg_raw.lower())
        if fix_obj:
            new_lines.append(f"{pkg_raw}>={fix_obj.fixed_version}")
            applied_fixes.append(fix_obj)
        else:
            new_lines.append(line)

    trailing = "\n" if req_content.endswith("\n") else ""
    return "\n".join(new_lines) + trailing, tuple(applied_fixes)
