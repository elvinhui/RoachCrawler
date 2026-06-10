import os
import sqlite3
import time
import random
import requests
from pytrends.request import TrendReq

# 锁定数据库路径在根目录
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'roach_matrix.db')

# 核心种子词库
SEED_MATRIX = [
    "Dell PowerEdge",
    "Redfish API",
    "iDRAC",
    "Cisco CCNA",
    "VLAN config",
    "Data Center HVAC"
]

# 意图修饰词过滤
INTENT_MODIFIERS = ["how to", "error", "failed", "vs", "tutorial", "code", "guide", "issue"]

def init_db():
    if not os.path.exists(DB_PATH):
        print(f"[-] 数据库 {DB_PATH} 不存在，请先初始化 core_db.py。")
        return None
    return sqlite3.connect(DB_PATH)

def cross_validate_reddit(keyword):
    """
    通过 Reddit API 搜索进行交叉验证。
    如果能找到相关讨论，认为是高优 P0 词。
    """
    forums = ["homelab", "ccna", "sysadmin"]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"}
    
    for forum in forums:
        url = f"https://www.reddit.com/r/{forum}/search.json?q={requests.utils.quote(keyword)}&restrict_sr=1&type=link"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                children = data.get("data", {}).get("children", [])
                if len(children) > 0:
                    return True  # 发现大量提问
        except Exception as e:
            pass
        time.sleep(1) # 防封控
    return False

def generate_expected_structure(keyword):
    if "vs" in keyword.lower():
        return f"生成标准的 B2B 评测格式，包含对比对象的详细参数表格，并深入分析应用场景下的优劣。"
    elif "error" in keyword.lower() or "failed" in keyword.lower() or "issue" in keyword.lower():
        return f"生成详细的技术排错指南（Troubleshooting Guide）。必须包含问题重现、日志分析、以及具体解决该报错的具体步骤或代码/CLI 命令。"
    else:
        return f"生成专业的技术教程或概念解析（Tutorial/Guide）。需包含清晰的步骤、示例代码或配置片段，以及该技术的最佳实践注意事项。"

def run_crawler():
    conn = init_db()
    if not conn:
        return

    cursor = conn.cursor()
    print("[*] 正在唤醒 Data Crawler & Trend Analyzer...")
    
    try:
        pytrends = TrendReq(hl='en-US', tz=360)
    except Exception as e:
        print(f"[-] pytrends 初始化失败 (可能需代理): {e}")
        return

    total_injected = 0

    for seed in SEED_MATRIX:
        print(f"\n[*] 正在拉取 Google Trends 种子词飙升趋势: {seed}")
        try:
            pytrends.build_payload([seed], timeframe='today 1-m') # 过去30天
            related = pytrends.related_queries()
        except Exception as e:
            print(f"[-] 拉取 {seed} 失败: {e}")
            time.sleep(5)
            continue
        
        if seed not in related or not related[seed]['rising'] is not None:
            print(f"[*] {seed} 暂无飙升词汇")
            continue
        
        rising_df = related[seed]['rising']
        
        for index, row in rising_df.iterrows():
            query = row['query']
            
            # 过滤高意图修饰词
            has_intent = any(mod in query.lower() for mod in INTENT_MODIFIERS)
            if not has_intent:
                continue
                
            print(f"[+] 发现高意图趋势词: '{query}'")
            
            # 论坛交叉验证
            is_p0 = cross_validate_reddit(query)
            niche = "IT_Infrastructure"
            intent = "troubleshooting_or_guide"
            
            expected_structure = generate_expected_structure(query)
            if is_p0:
                expected_structure += " 【注意：此话题在 Reddit/技术社区热度极高，请深入探讨并解决社区痛点】"

            try:
                # status 为 pending，优先级靠前的可以设定，此处直接按时间顺序让 sniffer 去抓
                cursor.execute('''
                INSERT INTO seo_matrix (keyword, intent, niche, expected_structure, status)
                VALUES (?, ?, ?, ?, 'pending')
                ''', (query, intent, niche, expected_structure))
                total_injected += 1
                print(f"  -> [P0={is_p0}] 已注入矩阵排队池！")
            except sqlite3.IntegrityError:
                print(f"  -> 跳过: '{query}' (矩阵中已存在)")

        time.sleep(random.uniform(2, 5)) # 防封控休眠

    conn.commit()
    conn.close()
    print(f"\n[+] Data Crawler 执行完毕。本次成功向底层矩阵注入 {total_injected} 个高优长尾词！")

if __name__ == "__main__":
    run_crawler()
