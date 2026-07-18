"""
quality_gate.py — Post-Generation Content Quality Gate
Validates all posts in site_payload/content/posts/ before they can be committed.
Catches thin content, missing frontmatter fields, broken JSON-LD, and AI cliché phrases.
Posts that fail are moved to a quarantine/ folder.
"""
import os
import re
import sys
import shutil
import yaml
import statistics
import subprocess
from datetime import datetime

def get_git_changed_files():
    """Returns absolute paths of all changed/untracked files in the git repo."""
    try:
        repo_root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).decode('utf-8').strip()
        untracked = subprocess.check_output(['git', 'ls-files', '-o', '--exclude-standard']).decode('utf-8').splitlines()
        modified = subprocess.check_output(['git', 'ls-files', '-m']).decode('utf-8').splitlines()
        staged = subprocess.check_output(['git', 'diff', '--name-only', '--cached']).decode('utf-8').splitlines()
        changed = set(untracked + modified + staged)
        return set(os.path.abspath(os.path.join(repo_root, f)) for f in changed)
    except Exception:
        return set()

POSTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'site_payload', 'content', 'posts'))
QUARANTINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'quarantine'))

# ── Quality thresholds ────────────────────────────────────────────────────────
MIN_WORD_COUNT = 800
MIN_H2_HEADINGS = 3

# ── Banned AI phrases ────────────────────────────────────────────────────────
BANNED_PHRASES_EN = [
    "in today's rapidly evolving",
    "it's worth noting that",
    "in the ever-changing landscape",
    "let's dive in",
    "without further ado",
    "game-changer",
    "comprehensive guide",
    "whether you're a seasoned",
    "navigating the complexities",
    "unlock the power",
    "at the end of the day",
    "harness the power",
    "delve into",
    "revolutionize",
    "robust solution",
]

BANNED_PHRASES_ZH = [
    "在当今快速发展的",
    "值得注意的是",
    "让我们深入探讨",
    "不容忽视",
    "毋庸置疑",
    "综上所述",
    "赋能",
    "一站式",
    "保姆级",
    "深度赋能",
    "全方位",
    "多维度",
    "颠覆性",
    "划时代",
]


def parse_frontmatter(content):
    """Extract YAML frontmatter and body from markdown content."""
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not match:
        return None, content
    try:
        fm = yaml.safe_load(match.group(1))
        body = match.group(2)
        return fm, body
    except yaml.YAMLError:
        return None, content


def count_words(text):
    """Count words, handling both CJK and Latin text."""
    # Remove markdown code blocks
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Count CJK characters as words
    cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))
    # Count Latin words
    latin_words = len(re.findall(r'[a-zA-Z]+', text))
    return cjk_chars + latin_words


def calculate_burstiness(text):
    """Calculate sentence length variation (standard deviation). High = human-like, Low = AI-like."""
    # Clean out markdown and code
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    # Split by English or Chinese punctuation
    sentences = re.split(r'[.!?。！？]+', text)
    lengths = []
    for s in sentences:
        s = s.strip()
        if len(s) > 2:  # Ignore empty or tiny remnants
            # Count words/characters
            cjk = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', s))
            latin = len(re.findall(r'[a-zA-Z]+', s))
            lengths.append(cjk + latin)
    
    if len(lengths) < 5:
        return 0
    return statistics.stdev(lengths)


def validate_post(filepath):
    """Validate a single post file. Returns (pass, list_of_issues)."""
    issues = []
    filename = os.path.basename(filepath)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return False, [f"Cannot read file: {e}"]

    # Skip index files
    if filename.startswith('_index'):
        return True, []

    # ── 1. Parse frontmatter ──────────────────────────────────────────────
    fm, body = parse_frontmatter(content)
    if fm is None:
        issues.append("CRITICAL: No valid YAML frontmatter found")
        return False, issues

    # ── 2. Required frontmatter fields ────────────────────────────────────
    if not fm.get('title'):
        issues.append("Missing frontmatter: title")
    if not fm.get('date'):
        issues.append("Missing frontmatter: date")
    if fm.get('draft', False) is True:
        issues.append("Post is marked as draft")
    if not fm.get('categories'):
        issues.append("Missing frontmatter: categories")

    # Description check (warning, not blocking)
    if not fm.get('description'):
        issues.append("WARNING: Missing frontmatter 'description' (hurts SEO meta tags)")

    # Cover image check
    cover = fm.get('cover', {})
    if not cover or not cover.get('image'):
        issues.append("WARNING: No cover image (reduces visual appeal and engagement)")

    # ── 3. Word count ─────────────────────────────────────────────────────
    wc = count_words(body)
    if wc < MIN_WORD_COUNT:
        issues.append(f"THIN CONTENT: {wc} words (minimum {MIN_WORD_COUNT})")

    # ── 4. Structure checks ───────────────────────────────────────────────
    h2_count = len(re.findall(r'^## ', body, re.MULTILINE))
    if h2_count < MIN_H2_HEADINGS:
        issues.append(f"Insufficient H2 headings: {h2_count} found (minimum {MIN_H2_HEADINGS})")

    # Table check
    table_rows = len(re.findall(r'^\|.*\|', body, re.MULTILINE))
    if table_rows < 3:
        issues.append("WARNING: No substantial markdown table found (comparison data expected)")

    # Code block check (technical blog should have code examples)
    code_blocks = len(re.findall(r'```', body))
    if code_blocks < 2:  # At least one open+close pair
        issues.append("WARNING: No code blocks found (technical articles should include examples)")

    # FAQ section check
    if 'FAQ' not in body and 'faq' not in body.lower() and 'frequently asked' not in body.lower():
        issues.append("WARNING: No FAQ section found")

    # References section check
    if 'references' not in body.lower() and 'community insights' not in body.lower():
        issues.append("WARNING: No References section found")

    # ── 5. Ad shortcode check (made-for-ads signal) ──────────────────────
    if re.search(r'\{\{<\s*ad300\s*>\}\}', body):
        issues.append("Ad shortcode {{< ad300 >}} detected (remove before AdSense review)")

    # ── 6. JSON-LD validation ─────────────────────────────────────────────
    jsonld_starts = [m.start() for m in re.finditer(r'<script type="application/ld\+json">', body)]
    jsonld_ends = [m.start() for m in re.finditer(r'</script>', body)]
    if len(jsonld_starts) > len(jsonld_ends):
        issues.append("CRITICAL: Unclosed JSON-LD <script> tag (will break page rendering)")

    # ── 7. Banned AI phrases ──────────────────────────────────────────────
    body_lower = body.lower()
    is_chinese = filename.endswith('.zh.md')
    banned_list = BANNED_PHRASES_ZH if is_chinese else BANNED_PHRASES_EN

    found_banned = []
    for phrase in banned_list:
        if phrase.lower() in body_lower:
            found_banned.append(phrase)
    if found_banned:
        issues.append(f"AI cliché phrases detected: {', '.join(found_banned[:3])}")

    # ── 8. Content uniqueness signals ─────────────────────────────────────
    # Check for first-person experience markers (E-E-A-T signal)
    first_person_markers = ['i ', 'i\'ve', 'i\'m', 'we ', 'our ', 'my ',
                            '我', '我们', '我的']
    has_first_person = any(marker in body.lower() for marker in first_person_markers)
    if not has_first_person:
        issues.append("WARNING: No first-person voice detected (E-E-A-T: experience signal missing)")

    # Check for specific numbers/data (concrete evidence)
    has_specific_data = bool(re.search(r'\d+\s*(MB|GB|TB|ms|IOPS|req/s|%|seconds|minutes|hours|dollars|\$)', body, re.IGNORECASE))
    if not has_specific_data:
        issues.append("WARNING: No specific metrics/numbers found (articles should cite concrete data)")

    # ── 9. Burstiness Score (AI Detection Evasion) ────────────────────────
    burstiness = calculate_burstiness(body)
    if burstiness < 8.0:
        issues.append(f"WARNING: Low burstiness score ({burstiness:.1f}). Sentences are too uniform, high risk of AI detection.")

    # ── Determine pass/fail ───────────────────────────────────────────────
    critical_issues = [i for i in issues if not i.startswith("WARNING")]
    passed = len(critical_issues) == 0

    return passed, issues


def get_new_posts():
    """Returns absolute paths of newly generated posts from new_posts.txt."""
    try:
        new_posts_path = os.path.join(os.path.dirname(__file__), 'new_posts.txt')
        if not os.path.exists(new_posts_path):
            return set()
        with open(new_posts_path, 'r', encoding='utf-8') as f:
            return set(os.path.abspath(line.strip()) for line in f if line.strip())
    except Exception:
        return set()


def run_quality_gate():
    """Scan all posts and quarantine failing ones."""
    if not os.path.exists(POSTS_DIR):
        print("[-] Posts directory not found. Nothing to validate.")
        return

    os.makedirs(QUARANTINE_DIR, exist_ok=True)
    
    if len(sys.argv) > 1:
        all_files = [os.path.abspath(f) for f in sys.argv[1:]]
    else:
        changed_files = get_new_posts()
        all_files = []
        for root, _, files in os.walk(POSTS_DIR):
            for f in files:
                if f.endswith('.md'):
                    abs_path = os.path.abspath(os.path.join(root, f))
                    if abs_path in changed_files:
                        all_files.append(os.path.relpath(abs_path, POSTS_DIR))

    if not all_files:
        print("[*] No posts found to validate.")
        return

    total = len(all_files)
    passed_count = 0
    failed_count = 0
    warning_count = 0

    print(f"[*] Quality Gate: Scanning {total} posts in {POSTS_DIR}...\n")

    for filename in sorted(all_files):
        filepath = os.path.join(POSTS_DIR, filename)
        passed, issues = validate_post(filepath)

        warnings = [i for i in issues if i.startswith("WARNING")]
        errors = [i for i in issues if not i.startswith("WARNING")]

        if passed and not errors:
            if warnings:
                warning_count += 1
                print(f"  [~] {filename}: PASS (with {len(warnings)} warnings)")
                for w in warnings:
                    print(f"      ⚠ {w}")
            else:
                print(f"  [+] {filename}: PASS")
            passed_count += 1
        else:
            print(f"  [✗] {filename}: FAIL")
            for issue in issues:
                prefix = "⚠" if issue.startswith("WARNING") else "✗"
                print(f"      {prefix} {issue}")

            # Move to quarantine
            quarantine_path = os.path.join(QUARANTINE_DIR, os.path.basename(filepath))
            shutil.move(filepath, quarantine_path)
            print(f"      → Quarantined to {quarantine_path}")
            failed_count += 1

    print(f"\n[*] Quality Gate Summary:")
    print(f"    ✓ Passed: {passed_count}")
    print(f"    ✗ Failed (quarantined): {failed_count}")
    print(f"    ⚠ Warnings: {warning_count}")

    if failed_count > 0:
        print(f"\n[!] {failed_count} post(s) quarantined. Review in: {QUARANTINE_DIR}")
        # Exit with error so pipeline can detect failures
        sys.exit(1)


if __name__ == '__main__':
    run_quality_gate()
