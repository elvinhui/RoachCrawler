"""
post_cleanup.py — Existing Post Quality Upgrade Script
Fixes issues in all existing posts to improve AdSense approval chances:

1. Removes {{< ad300 >}} shortcodes (78 posts affected — "made-for-ads" signal)
2. Removes draft posts and research dumps (79 drafts polluting the index)
3. Adds missing 'description' field to frontmatter (159 posts missing it)
4. Removes cover images pointing to remote pollinations.ai URLs (use local or remove)
5. Reports a quality summary

Run with --dry-run first to preview changes.
"""
import os
import re
import sys
import shutil
import yaml
import subprocess

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
REMOVED_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'quarantine', 'removed_drafts'))

DRY_RUN = '--dry-run' in sys.argv


def parse_frontmatter_raw(content):
    """Extract raw frontmatter string, parsed dict, and body."""
    match = re.match(r'^(---\s*\n)(.*?)\n(---\s*\n)(.*)', content, re.DOTALL)
    if not match:
        return None, None, None, content
    try:
        fm_str = match.group(2)
        fm = yaml.safe_load(fm_str)
        body = match.group(4)
        return match.group(1), fm, match.group(3), body
    except yaml.YAMLError:
        return None, None, None, content


def generate_description(title, body, lang='en'):
    """Generate a meta description from the title and first paragraph."""
    # Try to get the first meaningful paragraph (skip headings, blank lines)
    lines = body.strip().split('\n')
    first_para = ''
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and not stripped.startswith('```') and not stripped.startswith('|') and not stripped.startswith('>') and not stripped.startswith('-') and not stripped.startswith('*'):
            first_para = stripped
            break

    if first_para:
        # Clean markdown formatting
        desc = re.sub(r'\*\*([^*]+)\*\*', r'\1', first_para)  # Remove bold
        desc = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', desc)   # Remove links
        desc = re.sub(r'`([^`]+)`', r'\1', desc)                # Remove code
        # Truncate to 155 chars at word boundary
        if len(desc) > 155:
            desc = desc[:155].rsplit(' ', 1)[0] + '...'
        return desc
    else:
        # Fallback: use title
        return title


def count_words(text):
    """Count words for both CJK and Latin text."""
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    cjk = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))
    latin = len(re.findall(r'[a-zA-Z]+', text))
    return cjk + latin


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

def run_cleanup():
    if not os.path.exists(POSTS_DIR):
        print("[-] Posts directory not found.")
        return

    os.makedirs(REMOVED_DIR, exist_ok=True)

    changed_files = get_new_posts()
    all_files = []
    for root, _, files in os.walk(POSTS_DIR):
        for f in files:
            if f.endswith('.md') and f != '_index.en.md' and f != '_index.zh.md':
                abs_path = os.path.abspath(os.path.join(root, f))
                if abs_path in changed_files:
                    all_files.append(os.path.relpath(abs_path, POSTS_DIR))

    stats = {
        'total': len(all_files),
        'drafts_removed': 0,
        'ad_shortcodes_removed': 0,
        'descriptions_added': 0,
        'thin_content_flagged': 0,
        'research_dumps_removed': 0,
    }

    print(f"[*] Post Cleanup: Scanning {stats['total']} files...")
    if DRY_RUN:
        print("[*] DRY RUN MODE — no files will be modified\n")

    for filename in sorted(all_files):
        filepath = os.path.join(POSTS_DIR, filename)
        changes = []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  [!] Cannot read {filename}: {e}")
            continue

        opener, fm, closer, body = parse_frontmatter_raw(content)

        # ── 1. Remove draft posts and research dumps ──────────────────────
        if fm and fm.get('draft') is True:
            if 'research' in filename.lower() or 'Research' in fm.get('title', ''):
                stats['research_dumps_removed'] += 1
                label = "RESEARCH DUMP"
            else:
                stats['drafts_removed'] += 1
                label = "DRAFT"

            print(f"  [✗] {filename}: {label} → removing")
            if not DRY_RUN:
                dest = os.path.join(REMOVED_DIR, os.path.basename(filename))
                shutil.move(filepath, dest)
            continue

        if fm is None:
            print(f"  [!] {filename}: No valid frontmatter, skipping")
            continue

        modified = False

        # ── 2. Remove {{< ad300 >}} shortcodes ───────────────────────────
        if re.search(r'\{\{<\s*ad300\s*>\}\}', body):
            body = re.sub(r'\{\{<\s*ad300\s*>\}\}', '', body).rstrip() + '\n'
            changes.append('removed ad300 shortcode')
            stats['ad_shortcodes_removed'] += 1
            modified = True

        # ── 3. Add missing description ────────────────────────────────────
        if not fm.get('description'):
            lang = 'zh' if filename.endswith('.zh.md') else 'en'
            desc = generate_description(fm.get('title', ''), body, lang)
            fm['description'] = desc
            changes.append('added description')
            stats['descriptions_added'] += 1
            modified = True

        # ── 4. Check for thin content (flag only, don't remove) ──────────
        wc = count_words(body)
        if wc < 500:
            changes.append(f'THIN CONTENT ({wc} words)')
            stats['thin_content_flagged'] += 1

        # ── Write changes ─────────────────────────────────────────────────
        if modified and not DRY_RUN:
            # Reconstruct the file
            # Use yaml.dump for frontmatter to preserve additions
            fm_out = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
            new_content = f"---\n{fm_out}---\n{body}"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)

        if changes:
            status = ", ".join(changes)
            print(f"  [~] {filename}: {status}")

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"[*] Cleanup Summary {'(DRY RUN)' if DRY_RUN else ''}")
    print(f"    Total files scanned:      {stats['total']}")
    print(f"    Drafts removed:           {stats['drafts_removed']}")
    print(f"    Research dumps removed:    {stats['research_dumps_removed']}")
    print(f"    Ad shortcodes stripped:    {stats['ad_shortcodes_removed']}")
    print(f"    Descriptions added:        {stats['descriptions_added']}")
    print(f"    Thin content flagged:      {stats['thin_content_flagged']}")
    print(f"{'='*60}")

    if DRY_RUN:
        print("\n[*] Re-run without --dry-run to apply changes.")


if __name__ == '__main__':
    run_cleanup()
