import requests
import json
import os
from dotenv import load_dotenv

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
    # 你的高净值基建领域流量词
    TEST_KEYWORD = "best data center infrastructure management software 2026"
    deploy_recon_probe(TEST_KEYWORD)