import json
import os
import httpx
import random
from datetime import datetime
from dotenv import load_dotenv

# 强制挂载根目录的机密金库 (.env)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

def process_payload():
    # 1. 检查底层数据载荷
    cwd = os.path.dirname(__file__)
    data_path = os.path.join(cwd, "target_data.txt")
    if not os.path.exists(data_path):
        print("[-] 严重错误：未找到底层数据载荷 target_data.txt，流水线熔断。")
        return

    with open(data_path, "r", encoding="utf-8") as f:
        raw_data = f.read()

    # 2. 动态抽取大模型密钥
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("[-] 致命异常：未能从 .env 金库中读取到 DEEPSEEK_API_KEY")
        return

    # 3. 生成硬性约束参数，切断 LLM 的自由发挥空间
    random_seed = random.randint(1000, 9999)
    current_time = datetime.now().astimezone().isoformat()

    # 4. 注入强约束指令集 (Prompt Engineering)
    prompt = f"""
    You are an elite infrastructure engineer writing a technical blog post.
    Analyze the following scraped competitor data: {raw_data}
    
    STRICT REQUIREMENTS:
    1. Output ONLY raw text. NO markdown code blocks (like ```markdown).
    2. The output MUST START EXACTLY with the following YAML front matter block. 
       Replace 'YOUR_GENERATED_TITLE_HERE' with a professional, SEO-friendly tech title. DO NOT modify anything else in the YAML block.

---
title: "YOUR_GENERATED_TITLE_HERE"
date: {current_time}
draft: false
categories: ["Infrastructure"]
cover:
  image: "[https://loremflickr.com/1200/600/server,datacenter,python?lock=](https://loremflickr.com/1200/600/server,datacenter,python?lock=){random_seed}"
  alt: "Infrastructure Visualization"
  hiddenInList: false
  hiddenInSingle: false
---

    3. Below the YAML block, write a highly technical, engaging article summarizing the tools or data. 
    4. Tone: Pragmatic, zero fluff. Use H2 and H3 headers appropriately.
    """
    
    print("[*] 正在拉起大模型算力，开始进行数据清洗与静态载荷重塑...")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": prompt}]}
    
    try:
        # 5. 呼叫远端算力集群 (必须是纯净的 https 协议)
        r = httpx.post("[https://api.deepseek.com/chat/completions](https://api.deepseek.com/chat/completions)", headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()
        
        # 6. 数据格式清洗 (防火墙)：剥离 LLM 可能自带的反引号
        content = content.removeprefix("```markdown").removeprefix("```").removesuffix("```").strip()
            
        # 7. 定位并刷入 Hugo 的前端物理扇区
        output_dir = os.path.abspath(os.path.join(cwd, "../site_payload/content/posts"))
        os.makedirs(output_dir, exist_ok=True)
        
        # 使用时间戳生成绝对唯一的文件名
        file_name = f"auto-generated-{int(datetime.now().timestamp())}.md"
        out_path = os.path.join(output_dir, file_name)
        
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"[+] 载荷生成完毕！已成功刷入前端静态网段: {out_path}")
        
    except httpx.HTTPStatusError as exc:
        print(f"[-] 算力调度异常：网关返回错误状态码 {exc.response.status_code}")
    except Exception as e:
        print(f"[-] 算力调度异常，连接被重置或丢包: {e}")

if __name__ == "__main__":
    process_payload()