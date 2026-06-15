"""
trend_crawler.py — Multi-Source Keyword Discovery Engine
三层容灾架构：
  Layer 1: Hacker News Top Stories (Real-time tech trends, no rate limits)
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

# ── Core seed matrix (organized by vertical) ─────────────────────────────────
SEED_MATRIX = {
    "data_center": [
        "Dell PowerEdge", "HPE ProLiant", "Redfish API", "iDRAC",
        "server rack cooling", "PDU load", "Data Center HVAC",
    ],
    "networking": [
        "Cisco CCNA", "VLAN config", "OSPF routing", "BGP peering",
        "Cisco switch CLI", "Arista EOS", "MikroTik RouterOS",
    ],
    "cloud_devops": [
        "Terraform", "Ansible automation", "AWS EKS", "Azure AKS",
        "GitHub Actions", "ArgoCD", "Pulumi", "CloudFormation",
        "Kubernetes cluster", "Helm chart",
    ],
    "cybersecurity": [
        "Palo Alto firewall", "FortiGate NGFW", "Splunk SIEM",
        "CrowdStrike EDR", "zero trust architecture", "OWASP Top 10",
        "Nessus vulnerability scan", "Wireshark packet analysis",
    ],
    "developer_tools": [
        "VS Code extensions", "Docker compose", "PostgreSQL tuning",
        "Redis caching", "Git workflow", "Neovim config",
        "MongoDB vs PostgreSQL", "SQLite performance",
    ],
    "ai_ml_infra": [
        "NVIDIA A100 vs H100", "PyTorch distributed training",
        "MLflow experiment tracking", "Kubeflow pipeline",
        "vLLM inference", "CUDA optimization", "Ray cluster",
    ],
    "sre_observability": [
        "Prometheus monitoring", "Grafana dashboard", "Datadog APM",
        "ELK stack", "OpenTelemetry", "PagerDuty incident",
        "SLO error budget", "Jaeger tracing",
    ],
}

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
    "https://www.reddit.com/r/devops/top/.rss?t=week",
    "https://www.reddit.com/r/kubernetes/top/.rss?t=week",
    "https://www.reddit.com/r/netsec/top/.rss?t=week",
    "https://www.reddit.com/r/aws/top/.rss?t=week",
    "https://www.reddit.com/r/selfhosted/top/.rss?t=week",
    "https://www.reddit.com/r/MachineLearning/top/.rss?t=week",
]

REDDIT_HEADERS = {
    "User-Agent": "script:roachcrawler:v1.0 (by /u/elvinhui)"
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


def _detect_niche(text):
    """Detect which niche a keyword/title belongs to based on content."""
    t = text.lower()
    niche_signals = {
        'cybersecurity': ['security', 'firewall', 'vulnerability', 'cve', 'ransomware',
                          'zero trust', 'siem', 'edr', 'pentest', 'malware', 'exploit'],
        'ai_ml_infra': ['gpu', 'nvidia', 'cuda', 'pytorch', 'tensorflow', 'llm',
                        'machine learning', 'training', 'inference', 'mlflow', 'ml'],
        'cloud_devops': ['kubernetes', 'docker', 'terraform', 'ansible', 'aws', 'azure',
                         'gcp', 'ci/cd', 'devops', 'helm', 'argocd', 'cloud'],
        'sre_observability': ['monitoring', 'observability', 'prometheus', 'grafana',
                              'opentelemetry', 'incident', 'sre', 'slo', 'datadog'],
        'developer_tools': ['database', 'postgres', 'redis', 'mongodb', 'git', 'api',
                            'vscode', 'neovim', 'sqlite', 'mysql', 'container'],
        'networking': ['network', 'router', 'switch', 'vlan', 'cisco', 'bgp', 'ospf',
                       'dns', 'tcp', 'firewall'],
        'data_center': ['server', 'datacenter', 'rack', 'pdu', 'cooling', 'dell',
                        'hpe', 'idrac', 'vmware', 'proxmox', 'esxi'],
    }
    for niche, signals in niche_signals.items():
        if any(sig in t for sig in signals):
            return niche
    return 'IT_general'


# ── Layer 1: Hacker News Top Stories ──────────────────────────────────────────
def fetch_from_hacker_news(cursor):
    print("[*] Layer 1: Hacker News Top Stories")
    count = 0
    top_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
    
    try:
        resp = requests.get(top_url, timeout=10)
        if resp.status_code != 200:
            print("    [-] HN API fetch failed")
            return 0
            
        story_ids = resp.json()[:30] # Check top 30 stories
        
        # IT & Infrastructure relevant keywords (expanded for all verticals)
        it_keywords = [
            # Data Center & Hardware
            'server', 'datacenter', 'rack', 'pdu', 'cooling',
            # Networking
            'network', 'networking', 'router', 'switch', 'tcp', 'bgp', 'dns',
            # Cloud & DevOps
            'cloud', 'aws', 'azure', 'gcp', 'kubernetes', 'docker', 'terraform',
            'devops', 'ci/cd', 'ansible', 'helm', 'argocd',
            # Cybersecurity
            'security', 'firewall', 'vulnerability', 'cve', 'ransomware',
            'zero-trust', 'siem', 'edr', 'pentest',
            # Developer Tools & Databases
            'database', 'postgres', 'redis', 'mongodb', 'git', 'api',
            'linux', 'containers',
            # AI/ML
            'gpu', 'nvidia', 'cuda', 'pytorch', 'tensorflow', 'llm',
            'machine-learning', 'training', 'inference',
            # SRE & Observability
            'monitoring', 'observability', 'prometheus', 'grafana',
            'opentelemetry', 'incident', 'sre', 'infrastructure',
            'vmware',
        ]
        
        for sid in story_ids:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"
            item_resp = requests.get(item_url, timeout=5)
            if item_resp.status_code == 200:
                item = item_resp.json()
                title = item.get("title", "")
                
                # Check relevance
                if not any(kw in title.lower() for kw in it_keywords):
                    continue
                    
                # Hacker News often has "Show HN" or "Ask HN", we clean it
                clean_title = title.replace("Show HN: ", "").replace("Ask HN: ", "")
                
                structure = build_expected_structure(clean_title)
                niche = _detect_niche(clean_title)
                if inject_keyword(cursor, clean_title, 'hn_trending', niche, structure):
                    print(f"    [+] Injected (Hacker News, {niche}): {clean_title}")
                    count += 1
                    
    except Exception as e:
        print(f"    [-] Hacker News API error: {e}")
        
    return count


# ── Layer 2: Reddit RSS ───────────────────────────────────────────────────────
def fetch_from_reddit_rss(cursor):
    count = 0
    print("[*] Layer 2: Reddit RSS Top Posts (week)")

    # To prevent rate limiting from Reddit on GitHub Action IPs,
    # we only sample 2 subreddits per run.
    sampled_feeds = random.sample(REDDIT_FEEDS, min(2, len(REDDIT_FEEDS)))
    for feed_url in sampled_feeds:
        try:
            time.sleep(random.uniform(5, 8))
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

                # Only keep if it relates to our IT niche (expanded for all verticals)
                it_keywords = [
                    # Data Center & Hardware
                    'server', 'rack', 'pdu', 'ups', 'nas', 'data center',
                    'dell', 'hp', 'hpe', 'idrac', 'ilo', 'bmc', 'ipmi', 'redfish',
                    # Networking
                    'switch', 'router', 'vlan', 'cisco', 'unifi', 'pfsense',
                    'firewall', 'fiber', 'sfp', 'ccna', 'ospf', 'bgp',
                    'spanning tree', 'lag', 'lacp',
                    # Cloud & DevOps
                    'kubernetes', 'docker', 'ansible', 'terraform', 'helm',
                    'aws', 'azure', 'gcp', 'ci/cd', 'argocd', 'jenkins',
                    'github actions', 'pulumi', 'cloudformation',
                    # Virtualization
                    'esxi', 'vmware', 'proxmox', 'hyper-v',
                    # Cybersecurity
                    'siem', 'edr', 'zero trust', 'vulnerability', 'cve',
                    'pentest', 'ransomware', 'crowdstrike', 'palo alto',
                    # Developer Tools
                    'postgres', 'mysql', 'redis', 'mongodb', 'sqlite',
                    'git', 'vscode', 'neovim',
                    # AI/ML
                    'gpu', 'nvidia', 'cuda', 'pytorch', 'tensorflow',
                    'llm', 'training', 'inference', 'mlflow',
                    # SRE & Observability
                    'prometheus', 'grafana', 'datadog', 'elk', 'splunk',
                    'opentelemetry', 'pagerduty', 'slo', 'sre',
                    'linux', 'windows server', 'active directory', 'dns', 'dhcp', 'vpn',
                ]
                if not any(kw in title.lower() for kw in it_keywords):
                    continue

                structure = build_expected_structure(title)
                niche = _detect_niche(title)
                if inject_keyword(cursor, title, 'reddit_trending', niche, structure):
                    print(f"    [+] Injected (Reddit r/{subreddit}, {niche}): {title[:70]}...")
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
    print("[*] Layer 3: Programmatic SEO Combinatorial Expansion (Multi-Vertical)")
    count = 0

    # ── Template 1: Hardware vs Hardware (existing, scoped down) ──────────────
    hardware_a = [
        "Dell PowerEdge R760", "HPE ProLiant DL380 Gen11", "Cisco UCS C240 M7",
    ]
    hardware_b = [
        "Dell PowerEdge R660", "HPE ProLiant DL360 Gen11", "Cisco UCS C220 M7",
    ]
    hw_intents = [
        "power consumption comparison 2026",
        "IOPS benchmark test",
    ]
    for a, b, intent in itertools.product(hardware_a, hardware_b, hw_intents):
        if a.split()[0] == b.split()[0] and a.split()[1] == b.split()[1]:
            continue
        kw = f"{a} vs {b} {intent}"
        structure = build_expected_structure(kw)
        if inject_keyword(cursor, kw, 'programmatic_comparison', 'data_center', structure):
            count += 1

    # ── Template 2: Cloud/DevOps tool comparisons ────────────────────────────
    devops_pairs = [
        ("Terraform", "Pulumi", "cloud_devops"),
        ("GitHub Actions", "GitLab CI", "cloud_devops"),
        ("ArgoCD", "FluxCD", "cloud_devops"),
        ("AWS EKS", "Azure AKS", "cloud_devops"),
        ("Ansible", "SaltStack", "cloud_devops"),
        ("Docker Swarm", "Kubernetes", "cloud_devops"),
    ]
    devops_intents = [
        "comparison for production 2026",
        "migration guide",
        "cost and feature analysis",
    ]
    for (a, b, niche), intent in itertools.product(devops_pairs, devops_intents):
        kw = f"{a} vs {b} {intent}"
        structure = build_expected_structure(kw)
        if inject_keyword(cursor, kw, 'programmatic_comparison', niche, structure):
            count += 1

    # ── Template 3: How-to tutorials ─────────────────────────────────────────
    tutorial_subjects = [
        ("Terraform AWS VPC", "cloud_devops"),
        ("Kubernetes Ingress NGINX", "cloud_devops"),
        ("Ansible playbook Windows Server", "cloud_devops"),
        ("Docker multi-stage build optimization", "developer_tools"),
        ("PostgreSQL partitioning", "developer_tools"),
        ("Redis cluster", "developer_tools"),
        ("Prometheus alerting rules", "sre_observability"),
        ("Grafana dashboard provisioning", "sre_observability"),
        ("OpenTelemetry collector", "sre_observability"),
        ("Palo Alto GlobalProtect VPN", "cybersecurity"),
        ("Splunk SIEM correlation rules", "cybersecurity"),
        ("CrowdStrike Falcon sensor deployment", "cybersecurity"),
        ("PyTorch distributed training multi-GPU", "ai_ml_infra"),
        ("MLflow model registry", "ai_ml_infra"),
        ("vLLM serving deployment", "ai_ml_infra"),
    ]
    tutorial_intents = [
        "setup tutorial 2026",
        "configuration guide",
        "best practices",
    ]
    for (subject, niche), intent in itertools.product(tutorial_subjects, tutorial_intents):
        kw = f"{subject} {intent}"
        structure = build_expected_structure(kw)
        if inject_keyword(cursor, kw, 'programmatic_howto', niche, structure):
            count += 1

    # ── Template 4: Troubleshooting guides ───────────────────────────────────
    troubleshoot_topics = [
        ("Kubernetes pod CrashLoopBackOff", "cloud_devops"),
        ("Kubernetes ImagePullBackOff", "cloud_devops"),
        ("Terraform state lock", "cloud_devops"),
        ("Docker container OOMKilled", "developer_tools"),
        ("PostgreSQL connection refused", "developer_tools"),
        ("Redis memory fragmentation", "developer_tools"),
        ("Prometheus high cardinality", "sre_observability"),
        ("Grafana datasource connection error", "sre_observability"),
        ("VMware ESXi PSOD purple screen", "data_center"),
        ("iDRAC firmware update failed", "data_center"),
        ("FortiGate VPN tunnel down", "cybersecurity"),
        ("SSL certificate chain incomplete", "cybersecurity"),
        ("CUDA out of memory PyTorch", "ai_ml_infra"),
        ("NVIDIA driver version mismatch", "ai_ml_infra"),
    ]
    for topic, niche in troubleshoot_topics:
        kw = f"{topic} troubleshoot fix"
        structure = build_expected_structure(kw)
        if inject_keyword(cursor, kw, 'programmatic_troubleshoot', niche, structure):
            count += 1

    # ── Template 5: Top N rankings ───────────────────────────────────────────
    ranking_topics = [
        ("SIEM tools enterprise security", "cybersecurity"),
        ("Kubernetes monitoring solutions", "sre_observability"),
        ("open source CI/CD platforms", "cloud_devops"),
        ("GPU cloud providers for ML training", "ai_ml_infra"),
        ("PostgreSQL GUI clients", "developer_tools"),
        ("network monitoring tools", "networking"),
        ("server management platforms", "data_center"),
        ("incident management tools for SRE", "sre_observability"),
        ("container security scanners", "cybersecurity"),
        ("MLOps platforms", "ai_ml_infra"),
    ]
    for topic, niche in ranking_topics:
        kw = f"Top 5 {topic} 2026"
        structure = build_expected_structure(kw)
        if inject_keyword(cursor, kw, 'programmatic_ranking', niche, structure):
            count += 1

    print(f"    [+] Programmatic: injected {count} new diversified long-tail keywords")
    return count


# ── Main ──────────────────────────────────────────────────────────────────────
def run_crawler():
    conn = init_db()
    if not conn:
        return

    cursor = conn.cursor()
    total = 0

    print("[*] RoachCrawler Keyword Discovery Engine starting...\n")

    # Layer 1: Hacker News API (Reliable, fast, tech-focused)
    t1 = fetch_from_hacker_news(cursor)
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
