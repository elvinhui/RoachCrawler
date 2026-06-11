# scripts/core_db.py
import sqlite3
import os
from datetime import datetime
import itertools

# 锁定数据库路径在根目录
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'roach_matrix.db')


def init_db():
    """初始化底层流量矩阵数据库"""
    print(f"[*] 正在挂载底层数据库引擎: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 创建高维核心表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS seo_matrix (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT UNIQUE,
        intent TEXT,
        niche TEXT,
        expected_structure TEXT,
        status TEXT DEFAULT 'pending',  -- 状态: pending, processing, published, failed
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        published_at DATETIME
    )
    ''')

    # 给 status 字段加索引，极大提升流水线数万条数据时的查询速度
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON seo_matrix(status)')
    conn.commit()
    return conn


def generate_programmatic_keywords(conn):
    """
    Programmatic SEO: Multi-vertical keyword generation
    Generates diverse long-tail keywords across 7 IT verticals
    """
    cursor = conn.cursor()
    print("[*] 正在启动多垂直领域 Programmatic SEO 裂变引擎...")
    count = 0

    # ── Vertical 1: Data Center Hardware Comparisons ────────────────────────
    targets_A = ["Dell PowerEdge R760", "HPE ProLiant DL380 Gen11", "Cisco UCS C240 M7"]
    targets_B = ["Dell PowerEdge R660", "Lenovo ThinkSystem SR650", "Supermicro BigTwin"]
    hw_intents = [
        "power consumption comparison",
        "IOPS performance benchmark",
        "rack cooling guide",
    ]
    for a, b, intent in itertools.product(targets_A, targets_B, hw_intents):
        if a == b: continue
        kw = f"{a} vs {b} {intent} 2026"
        es = f"Generate a B2B comparison with detailed spec table for {a} vs {b}, analyzing {intent}."
        try:
            cursor.execute('INSERT INTO seo_matrix (keyword, intent, niche, expected_structure) VALUES (?, ?, ?, ?)',
                           (kw, 'b2b_hardware_comparison', 'data_center', es))
            count += 1
        except sqlite3.IntegrityError:
            pass

    # ── Vertical 2: Cloud & DevOps Tool Comparisons ─────────────────────────
    devops_pairs = [
        ("Terraform", "Pulumi"), ("GitHub Actions", "GitLab CI"),
        ("ArgoCD", "FluxCD"), ("AWS EKS", "Azure AKS"),
    ]
    devops_intents = ["comparison for production 2026", "migration guide", "cost analysis"]
    for (a, b), intent in itertools.product(devops_pairs, devops_intents):
        kw = f"{a} vs {b} {intent}"
        es = f"Compare {a} and {b} for {intent}, include feature matrix table and code examples."
        try:
            cursor.execute('INSERT INTO seo_matrix (keyword, intent, niche, expected_structure) VALUES (?, ?, ?, ?)',
                           (kw, 'devops_comparison', 'cloud_devops', es))
            count += 1
        except sqlite3.IntegrityError:
            pass

    # ── Vertical 3: Cybersecurity Guides ────────────────────────────────────
    security_topics = [
        ("FortiGate NGFW initial setup", "security_tutorial"),
        ("Splunk SIEM correlation rules", "security_tutorial"),
        ("Zero trust architecture implementation", "security_architecture"),
        ("CrowdStrike vs SentinelOne EDR", "security_comparison"),
    ]
    for topic, intent in security_topics:
        kw = f"{topic} guide 2026"
        es = f"Generate a professional {intent} guide for '{topic}' with step-by-step instructions and best practices."
        try:
            cursor.execute('INSERT INTO seo_matrix (keyword, intent, niche, expected_structure) VALUES (?, ?, ?, ?)',
                           (kw, intent, 'cybersecurity', es))
            count += 1
        except sqlite3.IntegrityError:
            pass

    # ── Vertical 4: Developer Tools & Databases ─────────────────────────────
    dev_topics = [
        ("PostgreSQL vs MySQL high traffic", "developer_comparison"),
        ("Redis caching best practices", "developer_tutorial"),
        ("Docker multi-stage build optimization", "developer_tutorial"),
        ("MongoDB vs PostgreSQL document storage", "developer_comparison"),
    ]
    for topic, intent in dev_topics:
        kw = f"{topic} guide 2026"
        es = f"Generate a technical deep-dive for '{topic}' with benchmarks, config examples, and comparison tables."
        try:
            cursor.execute('INSERT INTO seo_matrix (keyword, intent, niche, expected_structure) VALUES (?, ?, ?, ?)',
                           (kw, intent, 'developer_tools', es))
            count += 1
        except sqlite3.IntegrityError:
            pass

    # ── Vertical 5: AI/ML Infrastructure ────────────────────────────────────
    ml_topics = [
        ("NVIDIA H100 vs A100 LLM training benchmark", "ml_benchmark"),
        ("PyTorch distributed training multi-GPU setup", "ml_tutorial"),
        ("MLflow vs Weights and Biases comparison", "ml_comparison"),
        ("vLLM vs TGI inference serving", "ml_comparison"),
    ]
    for topic, intent in ml_topics:
        kw = f"{topic} 2026"
        es = f"Generate a professional ML infrastructure guide for '{topic}' with performance data and configuration examples."
        try:
            cursor.execute('INSERT INTO seo_matrix (keyword, intent, niche, expected_structure) VALUES (?, ?, ?, ?)',
                           (kw, intent, 'ai_ml_infra', es))
            count += 1
        except sqlite3.IntegrityError:
            pass

    # ── Vertical 6: SRE & Observability ─────────────────────────────────────
    sre_topics = [
        ("Prometheus vs Datadog monitoring cost comparison", "sre_comparison"),
        ("OpenTelemetry distributed tracing setup", "sre_tutorial"),
        ("Grafana dashboard provisioning as code", "sre_tutorial"),
        ("SLO error budget calculation guide", "sre_guide"),
    ]
    for topic, intent in sre_topics:
        kw = f"{topic} 2026"
        es = f"Generate a professional SRE/observability guide for '{topic}' with practical examples and tool comparisons."
        try:
            cursor.execute('INSERT INTO seo_matrix (keyword, intent, niche, expected_structure) VALUES (?, ?, ?, ?)',
                           (kw, intent, 'sre_observability', es))
            count += 1
        except sqlite3.IntegrityError:
            pass

    # ── Vertical 7: Networking Tutorials ─────────────────────────────────────
    net_topics = [
        ("Cisco CCNA subnetting cheat sheet", "cert_study"),
        ("BGP peering configuration guide", "networking_tutorial"),
        ("VLAN trunking troubleshoot", "networking_troubleshoot"),
    ]
    for topic, intent in net_topics:
        kw = f"{topic} 2026"
        es = f"Generate a networking guide for '{topic}' with CLI command examples and topology diagrams."
        try:
            cursor.execute('INSERT INTO seo_matrix (keyword, intent, niche, expected_structure) VALUES (?, ?, ?, ?)',
                           (kw, intent, 'networking', es))
            count += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    print(f"[+] 多垂直领域裂变完成！成功向矩阵注入 {count} 个多样化长尾词。")


if __name__ == "__main__":
    connection = init_db()
    generate_programmatic_keywords(connection)
    connection.close()