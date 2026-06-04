import requests
import json
import os
from dotenv import load_dotenv

# 强制挂载根目录的机密金库 (.env)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


def deploy_recon_probe(keyword_item, json_file_path, all_keywords):
    keyword = keyword_item.get("keyword")
    expected_structure = keyword_item.get("expected_structure", "进行深度技术分析。")

    api_key = os.getenv("SERP_API_KEY")
    if not api_key:
        print("[-] 致命异常：未能从 .env 金库中读取到 SERP_API_KEY")
        return

    print(f"[*] 探针点火。正在扫描 Niche 路由节点: '{keyword}'...")
    endpoint = "https://serpapi.com/search"

    # 构造探测包载荷
    params = {"engine": "google", "q": keyword, "api_key": api_key, "num": 4}

    try:
        print("[!] TCP 链路已建立，等待目标网关回包...")
        res = requests.get(endpoint, params=params, timeout=30)
        res.raise_for_status()

        response_data = res.json()

        # 1. 抓取自然流量节点
        organic_data = response_data.get("organic_results", [])
        extracted_organic = []
        for node in organic_data:
            extracted_organic.append({
                "title": node.get('title'),
                "snippet": node.get('snippet')
            })

        # 2. 抓取 PAA (People Also Ask)
        paa_data = response_data.get("related_questions", [])
        extracted_paa = []
        for node in paa_data:
            extracted_paa.append({
                "question": node.get('question'),
                "snippet": node.get('snippet')
            })

        # [核心升级] 组装高维数据载荷，把 expected_structure 传给下游
        final_payload = {
            "target_keyword": keyword,
            "expected_structure": expected_structure,  # 强制结构要求
            "organic_intel": extracted_organic,
            "paa_questions": extracted_paa
        }

        # 物理层数据交接
        relay_file = os.path.join(os.path.dirname(__file__), "target_data.txt")
        with open(relay_file, "w", encoding="utf-8") as f:
            json.dump(final_payload, f, ensure_ascii=False, indent=2)

        print(f"[+] 嗅探成功。截获 {len(extracted_organic)} 个核心节点与 {len(extracted_paa)} 个痛点提问。")
        print("[+] 数据载荷已成功落盘。")

        # 标记 JSON 中该词汇的状态为 processing (防止重复抓取)
        keyword_item["status"] = "processing"
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(all_keywords, f, ensure_ascii=False, indent=2)
        print("[+] 词库状态已更新为 processing。")

    except requests.exceptions.Timeout:
        print("[-] 探针坠毁：网络层超时。目标网关响应超过 30 秒，连接自动熔断。")
    except KeyboardInterrupt:
        print("\n[!] 收到宿主机人工中断信号 (SIGINT)。探针挂起，安全撤回。")
    except requests.exceptions.RequestException as e:
        print(f"[-] 探针坠毁，底层网络链路异常: {e}")


if __name__ == "__main__":
    # ==========================================
    # 从 keywords.json 读取流水线任务
    # ==========================================
    json_path = os.path.join(os.path.dirname(__file__), '..', 'keywords.json')

    if not os.path.exists(json_path):
        print(f"[-] 找不到词汇矩阵文件: {json_path}")
        exit()

    with open(json_path, 'r', encoding='utf-8') as f:
        all_keywords = json.load(f)

    # 寻找第一个状态为 pending 的任务
    target_item = None
    for item in all_keywords:
        if item.get("status") == "pending":
            target_item = item
            break

    if not target_item:
        print("[*] 所有的关键词节点均已处理完毕 (无 pending 状态)。流水线进入休眠。")
    else:
        print(f"[*] 动态弹药装填完毕。即将执行词库任务...")
        print(f"[*] =========================================")
        deploy_recon_probe(target_item, json_path, all_keywords)