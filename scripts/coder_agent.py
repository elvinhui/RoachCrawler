import json
import os
import httpx
import random
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
        raw_data = f.read()

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("[-] 致命异常：未能从 .env 金库中读取到 DEEPSEEK_API_KEY")
        return

    # 锁定核心参数
    random_seed = random.randint(1000, 9999)
    current_time = datetime.now().astimezone().isoformat()

    # 核心指令重构：强迫大模型在单次会话中，输出由唯一隔离墙切开的双语架构
    prompt = f"""
    You are an elite infrastructure engineer writing a technical blog post.
    Analyze the following scraped competitor data: {raw_data}

    STRICT REQUIREMENTS:
    1. Output ONLY raw text. NO markdown code blocks (like ```markdown).
    2. You must generate TWO versions of the post: first in Chinese, then in English.
    3. Separate the two versions EXACTLY with the string: ====LANG_SEPARATOR====

    [CHINESE VERSION REQUIREMENTS]
    Must start exactly with this YAML:
---
title: "生成一个专业的中文技术标题"
date: {current_time}
draft: false
categories: ["Infrastructure"]
cover:
  image: "[https://loremflickr.com/1200/600/server,datacenter,python?lock=](https://loremflickr.com/1200/600/server,datacenter,python?lock=){random_seed}"
  alt: "基建可视化"
  hiddenInList: false
  hiddenInSingle: false
---
    Followed by the technical article in Chinese.

    ====LANG_SEPARATOR====

    [ENGLISH VERSION REQUIREMENTS]
    Must start exactly with this YAML:
---
title: "Generate a Professional English Tech Title"
date: {current_time}
draft: false
categories: ["Infrastructure"]
cover:
  image: "[https://loremflickr.com/1200/600/server,datacenter,python?lock=](https://loremflickr.com/1200/600/server,datacenter,python?lock=){random_seed}"
  alt: "Infrastructure Visualization"
  hiddenInList: false
  hiddenInSingle: false
---
    Followed by the technical article in English.
    """

    print("[*] 正在拉起大模型双语算力，开始进行双向矩阵重构...")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": prompt}]}

    try:
        r = httpx.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()

        # 清洗可能自带的包裹反引号
        content = content.removeprefix("```markdown").removeprefix("```").removesuffix("```").strip()

        # ==========================================================
        # 这里就是你问的：双语分流与落盘核心逻辑
        # ==========================================================
        if "====LANG_SEPARATOR====" in content:
            # 物理切割大模型吐出来的双语文本
            chinese_content, english_content = content.split("====LANG_SEPARATOR====")
            chinese_content = chinese_content.strip()
            english_content = english_content.strip()

            # 定位 Hugo 前端统一存储扇区
            output_dir = os.path.abspath(os.path.join(cwd, "../site_payload/content/posts"))
            os.makedirs(output_dir, exist_ok=True)

            # 生成绝对唯一的对称时间戳前缀
            base_name = f"post-{int(datetime.now().timestamp())}"

            # 1. 写入中文版 (纯 .md 后缀)
            zh_path = os.path.join(output_dir, f"{base_name}.md")
            with open(zh_path, "w", encoding="utf-8") as f:
                f.write(chinese_content)

            # 2. 写入英文版 (.en.md 后缀，完美与中文版前缀对齐)
            en_path = os.path.join(output_dir, f"{base_name}.en.md")
            with open(en_path, "w", encoding="utf-8") as f:
                f.write(english_content)

            print(f"[+] 自动化双语矩阵对齐成功！")
            print(f"    -> 中文节点: {zh_path}")
            print(f"    -> 英文节点: {en_path}")
        else:
            print("[-] 异常：大模型未按照规定格式生成语言隔离墙，无法分流落盘。")

    except httpx.HTTPStatusError as exc:
        print(f"[-] 算力调度异常：网关返回错误状态码 {exc.response.status_code}")
    except Exception as e:
        print(f"[-] 算力调度异常: {e}")


if __name__ == "__main__":
    process_payload()