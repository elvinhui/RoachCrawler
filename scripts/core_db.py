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
    Programmatic SEO 核心算法：矩阵裂变
    在这里定义你的 A/B 对比库，瞬间生成海量长尾词
    """
    cursor = conn.cursor()

    # 词库维度 1：目标硬件/软件 A
    targets_A = ["Dell PowerEdge R760", "HPE ProLiant DL380 Gen11", "Cisco UCS C240 M7"]
    # 词库维度 2：目标硬件/软件 B
    targets_B = ["Dell PowerEdge R660", "Lenovo ThinkSystem SR650", "Supermicro BigTwin"]
    # 词库维度 3：用户搜索意图后缀
    intents = [
        "power consumption comparison",
        "IOPS performance benchmark",
        "enterprise virtualization best practices",
        "maintenance and rack cooling guide"
    ]

    print("[*] 正在启动 Programmatic SEO 裂变引擎...")
    count = 0

    # 笛卡尔积排列组合生成长尾词
    for a, b, intent in itertools.product(targets_A, targets_B, intents):
        if a == b: continue  # 排除自己跟自己对比

        long_tail_keyword = f"{a} vs {b} {intent} 2026"
        expected_structure = f"生成标准的 B2B 评测格式，包含 {a} 和 {b} 的详细参数对比表格，并深入分析 {intent} 场景下的优劣。"

        try:
            cursor.execute('''
            INSERT INTO seo_matrix (keyword, intent, niche, expected_structure)
            VALUES (?, ?, ?, ?)
            ''', (long_tail_keyword, 'b2b_hardware_comparison', 'data_center', expected_structure))
            count += 1
        except sqlite3.IntegrityError:
            pass  # 触发 UNIQUE 约束，说明该词已存在，静默跳过

    conn.commit()
    print(f"[+] 裂变完成！成功向矩阵注入 {count} 个极品长尾词。")


if __name__ == "__main__":
    connection = init_db()
    generate_programmatic_keywords(connection)
    connection.close()