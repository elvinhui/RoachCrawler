import json
import os
import httpx
import random
import re
from datetime import datetime
from dotenv import load_dotenv

# 强制挂载根目录的机密金库 (.env)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


def process_payload():
    cwd = os.path.dirname(__file__)
    data_path = os.path.join(cwd, "target_data.txt")
    if not os.path.exists(data_path):
        print("[-] 严重错误：未找到底层数据载荷 target_data.txt，流水线熔断。")
        return

    with open(data_path, "r", encoding="utf-8") as f:
        try:
            payload_data = json.load(f)
            keyword_context = payload_data.get("target_keyword", "Tech Update")
            # [核心微调1]：接住上游传来的强结构要求
            expected_structure = payload_data.get("expected_structure", "进行深度的技术与商业价值分析。")
            organic_text = json.dumps(payload_data.get("organic_intel", []), ensure_ascii=False)
            paa_text = json.dumps(payload_data.get("paa_questions", []), ensure_ascii=False)
        except json.JSONDecodeError:
            print("[-] 数据损坏：target_data.txt 不是合法的 JSON 格式。")
            return

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("[-] 致命异常：未能从 .env 金库中读取到 DEEPSEEK_API_KEY")
        return

    # 锁定核心参数
    random_seed = random.randint(1000, 9999)
    current_time = datetime.now().astimezone().isoformat()

    # [核心微调2]：将 expected_structure 强行注入给 DeepSeek
    prompt = f"""
    You are an elite infrastructure engineer and senior tech analyst.
    Your target topic is: "{keyword_context}"

    CRITICAL STRUCTURAL REQUIREMENT: 
    {expected_structure}

    Here is the scraped data you must analyze and synthesize:
    [Organic Results]: {organic_text}
    [People Also Ask / FAQs]: {paa_text}

    STRICT REQUIREMENTS:
    1. Output ONLY raw text. NO markdown code blocks (like ```markdown) wrapping the entire response.
    2. You must generate TWO complete versions of the post: first in Chinese, then in English.
    3. Separate the two versions EXACTLY with the string: ====LANG_SEPARATOR====

    [CONTENT QUALITY & SEO REQUIREMENTS (Applies to both versions)]
    - NEVER just summarize. You must add professional insights, technical nuances, or pros/cons.
    - MANDATORY: You must include at least one Markdown TABLE comparing key metrics, tools, or concepts derived from the data.
    - MANDATORY: You must include an "FAQ" section using the provided [People Also Ask] questions, answering them with hard technical facts.
    - Use H2 (##) and H3 (###) tags properly.

    [CHINESE VERSION REQUIREMENTS]
    Must start exactly with this YAML:
---
title: "生成一个包含 {keyword_context} 的硬核中文标题"
date: {current_time}
draft: false
categories: ["Infrastructure"]
tags: ["Tech", "Analysis"]
cover:
  image: "[https://loremflickr.com/1200/600/server,datacenter,python?lock=](https://loremflickr.com/1200/600/server,datacenter,python?lock=){random_seed}"
  alt: "基建可视化"
  hiddenInList: false
  hiddenInSingle: false
---
    Followed by the highly structured technical article in Chinese (including Table and FAQ).

    ====LANG_SEPARATOR====

    [ENGLISH VERSION REQUIREMENTS]
    Must start exactly with this YAML:
---
title: "Generate a hardcore English title for {keyword_context}"
date: {current_time}
draft: false
categories: ["Infrastructure"]
tags: ["Tech", "Analysis"]
cover:
  image: "[https://loremflickr.com/1200/600/server,datacenter,python?lock=](https://loremflickr.com/1200/600/server,datacenter,python?lock=){random_seed}"
  alt: "Infrastructure Visualization"
  hiddenInList: false
  hiddenInSingle: false
---
    Followed by the highly structured technical article in English (including Table and FAQ).
    """

    print("[*] 正在拉起大模型双语算力，执行带有信息增量约束的重构任务...")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": prompt}],
        "temperature": 0.4  # 保持较低温度，确保生成的表格和技术术语准确
    }

    try:
        # [核心微调3]：修正网络请求代码，去掉多余的 markdown 符号，设置 timeout=60
        r = httpx.post("(https://api.deepseek.com/chat/completions)",
                       headers=headers, json=payload, timeout=90)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()

        # 暴力清理可能残留的 markdown 包裹符
        content = re.sub(r'^```markdown\s*', '', content)
        content = re.sub(r'^```\s*', '', content)
        content = re.sub(r'\s*```$', '', content)

        if "====LANG_SEPARATOR====" in content:
            chinese_content, english_content = content.split("====LANG_SEPARATOR====")

            output_dir = os.path.abspath(os.path.join(cwd, "../site_payload/content/posts"))
            os.makedirs(output_dir, exist_ok=True)

            base_name = f"post-{int(datetime.now().timestamp())}"

            # 1. 写入中文版
            zh_path = os.path.join(output_dir, f"{base_name}.md")
            with open(zh_path, "w", encoding="utf-8") as f:
                f.write(chinese_content.strip())

            # 2. 写入英文版
            en_path = os.path.join(output_dir, f"{base_name}.en.md")
            with open(en_path, "w", encoding="utf-8") as f:
                f.write(english_content.strip())

            print(f"[+] 自动化双语矩阵对齐成功！")
            print(f"    -> 中文节点: {zh_path}")
            print(f"    -> 英文节点: {en_path}")
        else:
            print("[-] 异常：大模型未按照规定格式生成语言隔离墙，无法分流落盘。建议检查 Token 是否截断。")

    except httpx.HTTPStatusError as exc:
        print(f"[-] 算力调度异常：网关返回错误状态码 {exc.response.status_code}")
    except Exception as e:
        print(f"[-] 算力调度异常: {e}")


if __name__ == "__main__":
    process_payload()