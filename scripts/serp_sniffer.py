import requests
import json
import os
from dotenv import load_dotenv
import random
from datetime import datetime
# 强制挂载根目录的机密金库 (.env)
# __file__ 指向当前脚本所在路径，'..' 代表向上退回项目根目录
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

def deploy_recon_probe(keyword):
    # 动态抽取环境变量，彻底剥离明文密钥
    api_key = os.getenv("SERP_API_KEY")
    if not api_key:
        print("[-] 致命异常：未能从 .env 金库中读取到 SERP_API_KEY")
        return
        
    print(f"[*] 探针点火。正在扫描 Niche 路由节点: '{keyword}'...")
    endpoint = "https://serpapi.com/search"
    
    # 构造探测包载荷 (锁定前 3 名，降低大模型上下文噪音)
    params = {"engine": "google", "q": keyword, "api_key": api_key, "num": 3}
    
    try:
        print("[!] TCP 链路已建立，等待目标网关回包...")
        # 设置 30 秒超时，防止 WAF 代理池卡死导致死锁
        res = requests.get(endpoint, params=params, timeout=30)
        res.raise_for_status() 
        
        organic_data = res.json().get("organic_results", [])
        extracted_nodes = []
        
        for node in organic_data:
            extracted_nodes.append({
                "title": node.get('title'),
                "url": node.get('link'),
                "snippet": node.get('snippet')
            })
            
        # 物理层数据交接：将清洗后的 JSON 报文写入同级目录的中继文件
        relay_file = os.path.join(os.path.dirname(__file__), "target_data.txt")
        with open(relay_file, "w", encoding="utf-8") as f:
            json.dump(extracted_nodes, f, ensure_ascii=False, indent=2)
            
        print(f"[+] 嗅探成功。截获 {len(extracted_nodes)} 个高价值节点，数据载荷已落盘。")
        
    except requests.exceptions.Timeout:
        print("[-] 探针坠毁：网络层超时。目标网关响应超过 30 秒，连接自动熔断。")
    except KeyboardInterrupt:
        print("\n[!] 收到宿主机人工中断信号 (SIGINT)。探针挂起，安全撤回。")
    except requests.exceptions.RequestException as e:
        print(f"[-] 探针坠毁，底层网络链路异常: {e}")


if __name__ == "__main__":
    # ==========================================
    # 动态流量池：构建你的基建领域核心词汇矩阵
    # ==========================================
    target_matrix = [
        # 🟢 硅谷前沿 AI 科技与大模型动态 (最热科技新闻)
        "latest LLM breakthrough news tech",
        "OpenAI Google DeepSeek new AI model release",
        "top AI tech news trending",
        "AI agent platform updates and capabilities",  # 锁定复杂智能体的最新编排逻辑

        # 🔵 AI Agent 与开发框架赛道
        "latest AI agent framework GitHub",
        "open source AI agent tools",
        "autonomous AI agents breakthrough",

        # 🟡 Python 与自动化运维赛道
        "Python automation script GitHub trending",
        "Python web scraping techniques",
        "Python network automation tools",

        # 🟣 数据中心与云原生基建赛道
        "data center infrastructure management innovations",
        "cloud computing architecture trends",
        "data center cooling technology updates"
    ]

    # 1. 从矩阵中随机抽取一条核心攻击载荷
    base_keyword = random.choice(target_matrix)

    # 2. 抓取当前服务器的绝对月份和年份 (例如: "June 2026")
    current_time_suffix = datetime.now().strftime("%B %Y")

    # 3. 动态合成最终探针指令，强制 Google 网关交出最新鲜的数据
    dynamic_keyword = f"{base_keyword} {current_time_suffix}"

    print(f"[*] 动态弹药装填完毕。")
    print(f"[*] 本次流水线航向已锁定: [{dynamic_keyword}]")
    print(f"[*] =========================================")

    # 点火发射
    deploy_recon_probe(dynamic_keyword)