"""
Immutable domain models for RoachCrawler autonomous self-healing pipeline.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FailureContext:
    """Immutable snapshot of a failed GitHub Actions workflow run."""
    run_id: str
    workflow_name: str
    log_excerpt: str
    failed_files: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CodeHunk:
    """Immutable search-and-replace hunk for surgical code patching."""
    target: str
    replacement: str


@dataclass(frozen=True)
class DiagnosisResult:
    """
    Immutable AI diagnosis result.
    category must be one of:
      - 'TRANSIENT': Network/rate-limit/temporary glitch, safe to re-run directly
      - 'CODE_FIX': Selector/API/logic error with a verified file patch
      - 'CREDENTIALS_EXPIRED': API key/token expired, requires human secret update
      - 'UNFIXABLE': Cannot be safely patched automatically
    """
    category: str
    root_cause: str
    target_file: Optional[str] = None
    patched_content: Optional[str] = None
    patches: tuple[CodeHunk, ...] = ()
    secret_name: Optional[str] = None


@dataclass(frozen=True)
class VulnerabilityFix:
    """Immutable record of a dependency vulnerability version upgrade."""
    package_name: str
    current_version: str
    fixed_version: str
    requirements_file: str = ""
