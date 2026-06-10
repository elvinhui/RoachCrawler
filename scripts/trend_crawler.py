"""
trend_crawler.py — Multi-Source Keyword Discovery Engine
三层容灾架构：
  Layer 1: Google Trends via pytrends (rate-limited, may be blocked)
  Layer 2: Reddit RSS feeds (no API key, reliable)
  Layer 3: Programmatic combinatorial expansion (always works, local only)
"""
import os
import re
import sys
import sqlite3
import time
import random
import hashlib
import requests
import itertools
import xml.etree.ElementTree as ET

# Force UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'roach_matrix.db')

# ── Core seed matrix ─────────────────────────────────────────────────────────
SEED_MATRIX = [
    "Dell PowerEdge", "Redfish API", "iDRAC", "HPE ProLiant",
    "Cisco CCNA", "VLAN config", "OSPF routing", "Cisco switch CLI",
    "Data Center HVAC", "PDU load", "server rack cooling",
    "VMware ESXi", "Proxmox", "Kubernetes cluster", "Ansible automation",
]

INTENT_MODIFIERS = [
    "how to", "error", "failed", "vs", "tutorial", "fix", "issue",
    "not working", "guide", "configuration", "setup", "install",
    "troubleshoot", "best practice", "review", "comparison",
]

# ── Reddit RSS subreddits ────────────────────────────────────────────────────
REDDIT_FEEDS = [
    "https://www.reddit.com/r/homelab/top/.rss?t=week",
    "https://www.reddit.com/r/sysadmin/top/.rss?t=week",
    "https://www.reddit.com/r/ccna/top/.rss?t=week",
    "https://www.reddit.com/r/networking/top/.rss?t=week",
    "https://www.reddit.com/r/DataCenter/top/.rss?t=week",
]

REDDIT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RoachCrawler/1.0; keyword research bot)"
}


def init_db():
    if not os.path.exists(DB_PATH):
        print(f"[-] DB not found at {DB_PATH}. Run core_db.py first.")
        return None
    return sqlite3.connect(DB_PATH)


def inject_keyword(cursor, keyword, intent, niche, expected_structure):
    """Insert keyword into the matrix if not already present."""
    try:
        cursor.execute(
            "INSERT INTO seo_matrix (keyword, intent, niche, expected_structure, status) "
            "VALUES (?, ?, ?, ?, 'pending')",
            (keyword, intent, niche, expected_structure)
        )
        return True
    except sqlite3.IntegrityError:
        return False  # Already exists


def build_expected_structure(keyword):
    kw = keyword.lower()
    if any(w in kw for w in ["vs", "comparison", "review"]):
        return (f"Generate a professional B2B comparison article for '{keyword}'. "
                f"MUST include a detailed Markdown comparison table with specs, pros/cons. "
                f"Conclude with a clear recommendation for different use cases.")
    elif any(w in kw for w in ["error", "failed", "not working", "issue", "fix", "troubleshoot"]):
        return (f"Generate a step-by-step troubleshooting guide for '{keyword}'. "
                f"MUST include: symptom description, root cause analysis, "
                f"and numbered resolution steps with actual CLI commands or config snippets.")
    else:
        return (f"Generate a professional technical tutorial or deep-dive for '{keyword}'. "
                f"MUST include: clear step-by-step instructions, real config examples "
                f"or code blocks, and a best-practices summary table.")


# ── Layer 1: Google Trends ────────────────────────────────────────────────────
def fetch_from_google_trends(cursor):
    # GitHub Actions 共享 IP 必定被 429 封锁，直接跳过节省时间
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        print("[*] Layer 1: Google Trends — skipped in CI (shared IPs always rate-limited)")
        return 0

    count = 0
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='en-US', tz=0, timeout=(10, 20),
                            retries=1, backoff_factor=1.0)
    except Exception as e:
        print(f"[!] pytrends init failed: {e}")
        return 0

    print("[*] Layer 1: Google Trends")
    for seed in SEED_MATRIX:
        try:
            sleep_time = random.uniform(20, 40)
            print(f"    Waiting {sleep_time:.0f}s before querying '{seed}'...")
            time.sleep(sleep_time)

            pytrends.build_payload([seed], timeframe='today 1-m')
            related = pytrends.related_queries()

            if seed not in related or related[seed]['rising'] is None:
                print(f"    No rising queries for '{seed}'")
                continue

            rising_df = related[seed]['rising']
            for _, row in rising_df.iterrows():
                query = str(row['query'])
                if not any(mod in query.lower() for mod in INTENT_MODIFIERS):
                    continue

                structure = build_expected_structure(query)
                if inject_keyword(cursor, query, 'trends_discovery', 'IT_Infrastructure', structure):
                    print(f"    [+] Injected (Trends): {query}")
                    count += 1

        except Exception as e:
            err = str(e)
            if '429' in err:
                print(f"    [!] Rate limited on '{seed}'. Stopping Trends layer.")
                break
            else:
                print(f"    [-] Error on '{seed}': {e}")

    return count


# ── Layer 2: Reddit RSS ───────────────────────────────────────────────────────
def fetch_from_reddit_rss(cursor):
    count = 0
    print("[*] Layer 2: Reddit RSS Top Posts (week)")

    for feed_url in REDDIT_FEEDS:
        try:
            time.sleep(random.uniform(2, 4))
            resp = requests.get(feed_url, headers=REDDIT_HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"    [-] RSS fetch failed ({resp.status_code}): {feed_url}")
                continue

            root = ET.fromstring(resp.content)
            # RSS 2.0 namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom'}

            # Try both Atom and RSS formats
            entries = root.findall('.//item') or root.findall('.//atom:entry', ns)

            subreddit = feed_url.split('/r/')[1].split('/')[0]
            injected_this_feed = 0

            for entry in entries[:20]:  # Top 20 posts per subreddit
                # Get title
                title_el = entry.find('title')
                if title_el is None:
                    continue
                title = title_el.text or ''

                # Clean up title (Reddit RSS often includes HTML)
                title = re.sub(r'<[^>]+>', '', title).strip()
                if len(title) < 10 or len(title) > 120:
                    continue

                # Only keep posts with intent signals
                if not any(mod in title.lower() for mod in INTENT_MODIFIERS):
                    continue

                # Only keep if it relates to our IT niche
                it_keywords = [
                    'server', 'network', 'switch', 'router', 'vlan', 'data center',
                    'esxi', 'vmware', 'proxmox', 'nas', 'rack', 'pdu', 'ups',
                    'cisco', 'dell', 'hp', 'hpe', 'unifi', 'pfsense', 'firewall',
                    'kubernetes', 'docker', 'ansible', 'terraform', 'linux',
                    'windows server', 'active directory', 'dns', 'dhcp', 'vpn',
                    'fiber', 'sfp', 'idrac', 'ilo', 'bmc', 'ipmi', 'redfish',
                    'ccna', 'ospf', 'bgp', 'spanning tree', 'lag', 'lacp',
                ]
                if not any(kw in title.lower() for kw in it_keywords):
                    continue

                structure = build_expected_structure(title)
                niche = f'reddit_{subreddit}'
                if inject_keyword(cursor, title, 'reddit_trending', niche, structure):
                    print(f"    [+] Injected (Reddit r/{subreddit}): {title[:70]}...")
                    count += 1
                    injected_this_feed += 1

            print(f"    [~] r/{subreddit}: {injected_this_feed} new keywords")

        except ET.ParseError:
            print(f"    [-] XML parse error for {feed_url}")
        except Exception as e:
            print(f"    [-] Error fetching {feed_url}: {e}")

    return count


# ── Layer 3: Programmatic Combinatorial Expansion ─────────────────────────────
def fetch_from_programmatic(cursor):
    print("[*] Layer 3: Programmatic SEO Combinatorial Expansion")
    count = 0

    hardware_a = [
        "Dell PowerEdge R760", "HPE ProLiant DL380 Gen11", "Cisco UCS C240 M7",
        "Supermicro BigTwin", "Lenovo ThinkSystem SR650 V3",
    ]
    hardware_b = [
        "Dell PowerEdge R660", "HPE ProLiant DL360 Gen11", "Cisco UCS C220 M7",
        "Supermicro SuperServer", "Lenovo ThinkSystem SR630 V3",
    ]
    intents = [
        "power consumption comparison 2026",
        "IOPS benchmark test",
        "virtualization performance",
        "rack density cooling guide",
        "memory configuration guide",
        "NVMe storage benchmark",
    ]

    software_targets = [
        "iDRAC 9", "HPE iLO 6", "Redfish API", "VMware ESXi 8",
        "Proxmox VE 8", "Cisco IOS-XE",
    ]
    software_intents = [
        "configuration guide 2026",
        "error code fix",
        "automation script python",
        "best practices",
        "REST API tutorial",
    ]

    # Hardware vs hardware combos
    for a, b, intent in itertools.product(hardware_a, hardware_b, intents):
        if a == b:
            continue
        kw = f"{a} vs {b} {intent}"
        structure = build_expected_structure(kw)
        if inject_keyword(cursor, kw, 'programmatic_comparison', 'data_center', structure):
            count += 1

    # Software how-to combos
    for sw, intent in itertools.product(software_targets, software_intents):
        kw = f"{sw} {intent}"
        structure = build_expected_structure(kw)
        if inject_keyword(cursor, kw, 'programmatic_howto', 'IT_ops', structure):
            count += 1

    print(f"    [+] Programmatic: injected {count} new long-tail keywords")
    return count


# ── Main ──────────────────────────────────────────────────────────────────────
def run_crawler():
    conn = init_db()
    if not conn:
        return

    cursor = conn.cursor()
    total = 0

    print("[*] RoachCrawler Keyword Discovery Engine starting...\n")

    # Layer 1: Google Trends (best quality, but may be rate-limited)
    t1 = fetch_from_google_trends(cursor)
    conn.commit()
    total += t1
    print(f"[~] Layer 1 result: {t1} keywords\n")

    # Layer 2: Reddit RSS (reliable, no API key needed)
    t2 = fetch_from_reddit_rss(cursor)
    conn.commit()
    total += t2
    print(f"[~] Layer 2 result: {t2} keywords\n")

    # Layer 3: Programmatic (always runs, fills the queue)
    t3 = fetch_from_programmatic(cursor)
    conn.commit()
    total += t3
    print(f"[~] Layer 3 result: {t3} keywords\n")

    conn.close()
    print(f"[+] Discovery complete. Total new keywords injected: {total}")


if __name__ == '__main__':
    run_crawler()
