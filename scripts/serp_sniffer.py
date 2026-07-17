import requests
import json
import os
import sqlite3
from datetime import datetime, date
from dotenv import load_dotenv

# 强制挂载根目录的机密金库 (.env)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# AdSense 合规：每日发布上限，防止被 Google 判定为内容农场
MAX_DAILY_PUBLISH = 3


def check_daily_limit():
    """检查今天已经发布了多少篇文章，超限则跳过"""
    db_path = os.path.join(os.path.dirname(__file__), '..', 'roach_matrix.db')
    if not os.path.exists(db_path):
        return False  # DB 不存在，不限制

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    today = date.today().strftime("%Y-%m-%d")
    cursor.execute(
        "SELECT COUNT(*) FROM seo_matrix WHERE status = 'published' AND published_at LIKE ?",
        (f"{today}%",)
    )
    count = cursor.fetchone()[0]
    conn.close()

    if count >= MAX_DAILY_PUBLISH:
        print(f"[*] 今日已发布 {count} 篇文章（上限 {MAX_DAILY_PUBLISH}），跳过本次生成以符合 AdSense 合规。")
        return True
    print(f"[*] 今日已发布 {count}/{MAX_DAILY_PUBLISH} 篇，剩余配额充足。")
    return False


def get_task_from_db():
    """从 SQLite 数据库获取一个 pending 的任务并上锁"""
    db_path = os.path.join(os.path.dirname(__file__), '..', 'roach_matrix.db')
    if not os.path.exists(db_path):
        print(f"[-] 找不到数据库文件: {db_path}。请先运行 core_db.py 初始化并生成矩阵。")
        return None

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 寻找第一个排队的任务
    # Niche rotation: prioritize niches with fewest published articles to ensure diversity
    cursor.execute("""
        SELECT id, keyword, expected_structure, niche FROM seo_matrix
        WHERE status = 'pending'
        ORDER BY
            (SELECT COUNT(*) FROM seo_matrix AS s2
             WHERE s2.niche = seo_matrix.niche AND s2.status = 'published') ASC,
            RANDOM()
        LIMIT 1
    """)
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    task_id, keyword, expected_structure, niche = row

    # 立即上锁，将状态改为 processing，防止其他并发探针抢夺
    cursor.execute("UPDATE seo_matrix SET status = 'processing' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

    return {"id": task_id, "keyword": keyword, "expected_structure": expected_structure, "niche": niche}


def deploy_recon_probe(task):
    keyword = task.get("keyword")
    expected_structure = task.get("expected_structure")
    task_id = task.get("id")

    api_key = os.getenv("SERP_API_KEY")
    if not api_key:
        print("[-] 致命异常：未能从 .env 金库中读取到 SERP_API_KEY")
        return

    print(f"[*] 探针点火。正在扫描 Niche 路由节点: '{keyword}'...")
    endpoint = "https://serpapi.com/search"
    params = {"engine": "google", "q": keyword, "api_key": api_key, "num": 4}

    try:
        print("[!] TCP 链路已建立，等待目标网关回包...")
        res = requests.get(endpoint, params=params, timeout=30)
        res.raise_for_status()

        response_data = res.json()

        # 1. 抓取自然流量节点
        organic_data = response_data.get("organic_results", [])
        extracted_organic = [{"title": n.get('title'), "snippet": n.get('snippet')} for n in organic_data]

        # 2. 抓取 PAA (People Also Ask)
        paa_data = response_data.get("related_questions", [])
        extracted_paa = [{"question": n.get('question'), "snippet": n.get('snippet')} for n in paa_data]

        # ==========================================
        # [核心修复]：组装载荷时，强制注入 task_id
        # ==========================================
        final_payload = {
            "task_id": task_id,
            "target_keyword": keyword,
            "expected_structure": expected_structure,
            "niche": task.get("niche", "IT_general"),
            "organic_intel": extracted_organic,
            "paa_questions": extracted_paa
        }

        # 物理层数据交接：将清洗后的 JSON 报文写入同级目录
        relay_file = os.path.join(os.path.dirname(__file__), "target_data.txt")
        with open(relay_file, "w", encoding="utf-8") as f:
            json.dump(final_payload, f, ensure_ascii=False, indent=2)

        print(f"[+] 嗅探成功。截获 {len(extracted_organic)} 个核心节点与 {len(extracted_paa)} 个痛点提问。")
        print(f"[+] 数据载荷 (包含 Task ID: {task_id}) 已成功落盘。")

    except requests.exceptions.Timeout:
        print("[-] 探针坠毁：网络层超时。目标网关响应超过 30 秒，连接自动熔断。")
    except KeyboardInterrupt:
        print("\n[!] 收到宿主机人工中断信号 (SIGINT)。探针挂起，安全撤回。")
    except requests.exceptions.RequestException as e:
        print(f"[-] 探针坠毁，底层网络链路异常: {e}")


if __name__ == "__main__":
    print("[*] 正在连接 SQLite 矩阵中枢...")

    # AdSense 合规：每日发布速率限制
    if check_daily_limit():
        print("[*] 已达今日发布上限，流水线安全退出。")
    else:
        task = get_task_from_db()

        if not task:
            print("[*] 矩阵中所有长尾词节点均已打光！流水线进入休眠。")
        else:
            print(f"[*] 锁定目标节点 ID: {task['id']} -> [{task['keyword']}]")
            print(f"[*] =========================================")
            deploy_recon_probe(task)