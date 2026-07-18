import json
import os
import httpx
import random
import re
import sqlite3  # [新增] 引入 SQLite 库用于任务核销
import unicodedata
from datetime import datetime
from dotenv import load_dotenv

# 强制挂载根目录的机密金库 (.env)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# 动态分类映射：根据上游 niche 字段自动匹配文章分类
CATEGORY_MAP = {
    "data_center": ("Data Center", "infrastructure engineer and data center specialist"),
    "networking": ("Networking", "network engineer and CCNA/CCNP specialist"),
    "cloud_devops": ("Cloud & DevOps", "cloud architect and DevOps engineer"),
    "cybersecurity": ("Cybersecurity", "cybersecurity analyst and penetration testing specialist"),
    "developer_tools": ("Developer Tools", "senior backend engineer and database specialist"),
    "ai_ml_infra": ("AI & ML Infrastructure", "ML infrastructure engineer and GPU computing specialist"),
    "sre_observability": ("SRE & Observability", "site reliability engineer and observability specialist"),
}
DEFAULT_CATEGORY = ("Infrastructure", "infrastructure engineer and senior tech analyst")

def resolve_category(niche):
    """Map niche tag to (category_name, role_description) tuple."""
    return CATEGORY_MAP.get(niche, DEFAULT_CATEGORY)


def slugify(text, max_length=60):
    """Convert text to a URL-safe slug for SEO-friendly filenames."""
    # Normalize unicode
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    # Lowercase
    text = text.lower()
    # Remove non-alphanumeric characters (except hyphens and spaces)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    # Replace spaces and multiple hyphens with single hyphen
    text = re.sub(r'[\s-]+', '-', text).strip('-')
    # Truncate to max_length at word boundary
    if len(text) > max_length:
        text = text[:max_length].rsplit('-', 1)[0]
    return text or 'post'


def process_payload():
    cwd = os.path.dirname(__file__)
    data_path = os.path.join(cwd, "target_data.txt")
    if not os.path.exists(data_path):
        print("[-] 严重错误：未找到底层数据载荷 target_data.txt，流水线熔断。")
        return

    with open(data_path, "r", encoding="utf-8") as f:
        try:
            payload_data = json.load(f)
            # [新增]：提取上游传过来的 task_id，用于后续数据库核销
            task_id = payload_data.get("task_id")
            keyword_context = payload_data.get("target_keyword", "Tech Update")
            expected_structure = payload_data.get("expected_structure", "进行深度的技术与商业价值分析。")
            niche = payload_data.get("niche", "data_center")
            organic_text = json.dumps(payload_data.get("organic_intel", []), ensure_ascii=False)
            paa_text = json.dumps(payload_data.get("paa_questions", []), ensure_ascii=False)
        except json.JSONDecodeError:
            print("[-] 数据损坏：target_data.txt 不是合法的 JSON 格式。")
            return

    # [新增] 读取社交舆情数据 (last30days 引擎生成)
    social_data_path = os.path.join(cwd, "target_social_data.txt")
    social_text = "No recent social data available."
    if os.path.exists(social_data_path):
        try:
            with open(social_data_path, "r", encoding="utf-8") as sf:
                social_text = sf.read()
        except Exception as e:
            print(f"[-] 读取 target_social_data.txt 异常: {e}")

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("[-] 致命异常：未能从 .env 金库中读取到 DEEPSEEK_API_KEY")
        return

    import urllib.parse
    
    # 锁定核心参数
    random_seed = random.randint(1000, 9999)
    current_time = datetime.now().astimezone().isoformat()
    category_name, role_desc = resolve_category(niche)
    
    # 动态生成基于 Prompt 的无版权极客封面图 (非硬编码)
    prompt_str = f"High quality technology photography representing {category_name} and {niche}, tech data center, 8k resolution"
    encoded_prompt = urllib.parse.quote(prompt_str)
    cover_image_url_remote = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1200&height=600&nologo=true&seed={random_seed}"
    image_filename = f"cover_{int(datetime.now().timestamp())}_{random_seed}.jpg"
    image_dir = os.path.abspath(os.path.join(cwd, "../site_payload/static/images"))
    os.makedirs(image_dir, exist_ok=True)
    image_path = os.path.join(image_dir, image_filename)
    try:
        import httpx
        print(f"[*] Downloading cover image to {image_path}...")
        img_resp = httpx.get(cover_image_url_remote, timeout=30)
        img_resp.raise_for_status()
        with open(image_path, "wb") as f:
            f.write(img_resp.content)
        cover_image_url = f"/images/{image_filename}"
    except Exception as e:
        print(f"[-] Image download failed, using remote fallback: {e}")
        cover_image_url = cover_image_url_remote

    # 核心指令重构：强加“信息增量”限制与双语隔离墙
    prompt = f"""
    You are an elite {role_desc}.
    Your target topic is: "{keyword_context}"

    CRITICAL STRUCTURAL REQUIREMENT: 
    {expected_structure}

    Here is the scraped data you must analyze and synthesize:
    [Organic Results (Google)]: {organic_text}
    [People Also Ask / FAQs]: {paa_text}
    [Social Sentiment (Last 30 Days from Reddit/HN/X)]: 
    {social_text}

    CRITICAL INSIGHT REQUIREMENT:
    You MUST heavily leverage the [Social Sentiment] data. Quote real user complaints, reference recent community backlash or trends, and use these human signals to make the article highly engaging, contrarian, or uniquely insightful. Do not just summarize; inject these raw realities into your technical narrative.

    STRICT REQUIREMENTS:
    1. Output ONLY raw text. NO markdown code blocks (like ```markdown) wrapping the entire response.
    2. You must generate TWO complete versions of the post: first in Chinese, then in English.
    3. Separate the two versions EXACTLY with the string: ====LANG_SEPARATOR====

    [HUMAN WRITING STYLE — CRITICAL ANTI-AI-DETECTION RULES]
    You MUST write like a real senior engineer sharing hard-won experience, NOT like an AI assistant.
    Violating these rules will make the content flagged as AI-generated and worthless for SEO.

    BANNED PHRASES (never use these or similar AI clichés):
    - English: "In today's rapidly evolving", "It's worth noting that", "In the ever-changing landscape",
      "Let's dive in", "without further ado", "In conclusion", "game-changer", "it's important to note",
      "comprehensive guide", "Whether you're a seasoned", "navigating the complexities",
      "unlock the power", "at the end of the day", "leverage", "harness the power",
      "streamline", "empower", "delve into", "revolutionize", "robust solution",
      "Furthermore", "Moreover", "Additionally", "Crucially", "Consequently", "As a result",
      "picture this", "imagine if you will", "fast forward to", "the realm of", "meticulous"
    - Chinese: "在当今快速发展的", "值得注意的是", "总而言之", "让我们深入探讨", "不容忽视",
      "毋庸置疑", "综上所述", "赋能", "一站式", "保姆级", "助力", "深度赋能",
      "全方位", "多维度", "颠覆性", "划时代", "此外", "更重要的是", "毫无疑问",
      "想象一下", "在这个领域", "精心设计"

    MANDATORY WRITING TECHNIQUES (TO DEFEAT AI DETECTION):
    1. EXTREME BURSTINESS: You must wildly vary your sentence lengths. Write a 30-word complex technical run-on sentence. Then write a 3-word punchy sentence. "It failed." Never write 3 sentences of similar length in a row.
    2. HIGH PERPLEXITY VOCABULARY: Avoid predictable word pairings. Instead of "fast performance," say "blistering throughput." Instead of "hard to configure," say "a configuration nightmare." Use uncommon, specific technical idioms.
    3. FORMAT IMPERFECTIONS: Humans write messy markdown. Occasionally bold a weird phrase, use em-dashes (—) heavily instead of commas, and drop occasional rhetorical questions. Don't format every single list perfectly. 
    4. FIRST PERSON GRIT: Use "I", "we", "our team" naturally. Share specific, messy scenarios like "Last month we hit this exact issue on our prod cluster and it took us 3 hours to realize it was DNS" or "I personally tested this on a 3-node setup and the docs were completely wrong."
    5. OPINIONS & EDGE: Take clear stances. Say "X is frankly overpriced for what you get" or "I'd pick A over B nine times out of ten". Don't hedge everything with "may" and "might".
    6. SPECIFIC NUMBERS: Use concrete data points ("saved us 340ms per request", "dropped our P99 from 2.1s to 380ms") instead of vague claims ("significantly improved performance").
    7. NATURAL TRANSITIONS: Don't start every section with a smooth transition like "Moving on to...". Sometimes just jump in. Other times use casual connectors like "So here's where it gets interesting" or "Now, the part everyone gets wrong".
    8. COLLOQUIAL TOUCHES: Sprinkle in real engineer talk — "this blew up our monitoring", "we brute-forced the config", "the docs are garbage on this part".
    9. For Chinese: write in a conversational technical blog tone (技术博客口语化), NOT in a formal report style. Use "我" and "我们" naturally. Mix in common developer slang where appropriate (比如"踩坑"、"翻车"、"真香"、"白嫖", "直接被劝退", "跑路").

    [CONTENT QUALITY & SEO REQUIREMENTS (Applies to both versions)]
    - LENGTH & DEPTH (CRITICAL): The article MUST be extremely comprehensive, at least 1500 words per language. Do not write short fluff. Break down the topic into a highly logical flow:
        1. The Core Problem / Background (Why does this matter?)
        2. Architectural Deep Dive / Underlying Mechanisms (How does it work under the hood?)
        3. Real-world Implementation / Step-by-Step Breakdown (Concrete code, configs, or CLI examples)
        4. Performance, Cost, or Security Implications (The senior engineer's perspective)
        5. Alternatives and Trade-offs (What else is out there and why not use it?)
    - TITLE AND HEADINGS: Titles and H2/H3 headings MUST use highly specific, long-tail technical keywords (e.g., "Self-hosted MLflow Postgres backend setup and infrastructure cost" instead of "MLflow Review").
    - NEVER just summarize. You must add professional insights, technical nuances, or pros/cons.
    - MANDATORY: You must include at least one Markdown TABLE comparing key metrics, tools, or concepts derived from the data.
    - MANDATORY: Include Mermaid.js diagrams (using ```mermaid code blocks) if explaining architectures, workflows, or data pipelines.
    - MANDATORY: You must include an "FAQ" section using the provided [People Also Ask] questions, answering them with hard technical facts.
    - MANDATORY: You must include a "References & Community Insights" section at the end of the article (before the FAQ). You MUST include at least 3 REAL, SPECIFIC external URLs (e.g., official documentation, GitHub repositories, RFCs, or specific Reddit/HN discussion links) that are highly relevant to the topic. Do not just use a generic statement, actually provide a markdown list of URLs.
    - MANDATORY: At the very end of the article, you MUST generate a valid JSON-LD `FAQPage` schema block containing the FAQs you answered. Output it as raw HTML `<script type="application/ld+json">...</script>`.

    [CHINESE VERSION REQUIREMENTS]
    Must start exactly with this YAML:
---
title: "生成一个包含 {keyword_context} 的硬核中文标题"
date: {current_time}
draft: false
description: "用中文生成一个 120-160 字符的 SEO 元描述，必须包含核心关键词，吸引点击"
summary: "用中文写 2-3 句话概述文章核心观点"
categories: ["{category_name}"]
tags: ["Tech", "Analysis"]
cover:
  image: "{cover_image_url}"
  alt: "{category_name} 技术可视化"
  hiddenInList: false
  hiddenInSingle: false
---
    Followed by the highly structured technical article in Chinese (including Table and FAQ).
    MANDATORY: Start the article body with a "## 核心要点 (Key Takeaways)" section — a bullet list of 3-5 key insights the reader will gain. This dramatically improves user engagement and reduces bounce rate.

    ====LANG_SEPARATOR====

    [ENGLISH VERSION REQUIREMENTS]
    Must start exactly with this YAML:
---
title: "Generate a hardcore English title for {keyword_context}"
date: {current_time}
draft: false
description: "Generate a 120-160 character SEO meta description in English, must contain the core keyword, written to attract clicks"
summary: "Write 2-3 sentences summarizing the core insights of this article"
categories: ["{category_name}"]
tags: ["Tech", "Analysis"]
cover:
  image: "{cover_image_url}"
  alt: "{category_name} Visualization"
  hiddenInList: false
  hiddenInSingle: false
---
    Followed by the highly structured technical article in English (including Table and FAQ).
    MANDATORY: Start the article body with a "## Key Takeaways" section — a bullet list of 3-5 key insights the reader will gain. This dramatically improves user engagement and reduces bounce rate.
    """

    print("[*] 正在拉起大模型双语算力，执行带有信息增量约束的重构任务...")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": prompt}],
        "temperature": 0.85,  # 提高温度以增加文风多样性(Perplexity)，降低 AI 感，原 0.7
        "max_tokens": 16384  # 从 8192 提升至 16384，防止长文被截断导致 JSON-LD 损坏
    }

    try:
        # 5. 呼叫远端算力集群 (必须是纯净的 https 协议)
        r = httpx.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()

        # 暴力清理可能残留的 markdown 包裹符
        content = re.sub(r'^```markdown\s*', '', content)
        content = re.sub(r'^```\s*', '', content)
        content = re.sub(r'\s*```$', '', content)

        if "====LANG_SEPARATOR====" in content:
            chinese_content, english_content = content.split("====LANG_SEPARATOR====")

            # 自动修复由于 max_tokens 截断导致的 JSON-LD 标签未闭合问题
            def repair_json_ld(text):
                start_idx = text.rfind('<script type="application/ld+json">')
                if start_idx != -1:
                    end_idx = text.rfind('</script>', start_idx)
                    if end_idx == -1:
                        # 被截断！直接移除损坏的 script 块，防止 Hugo 编译报错
                        return text[:start_idx].rstrip()
                return text

            chinese_content = repair_json_ld(chinese_content)
            english_content = repair_json_ld(english_content)

            now = datetime.now()
            output_dir = os.path.abspath(os.path.join(cwd, "../site_payload/content/posts", str(now.year), f"{now.month:02d}"))
            os.makedirs(output_dir, exist_ok=True)

            # 使用关键词生成 SEO 友好的 URL slug（替代时间戳命名）
            base_name = slugify(keyword_context)
            # 如果 slug 已存在，追加短时间戳避免冲突
            if os.path.exists(os.path.join(output_dir, f"{base_name}.en.md")):
                base_name = f"{base_name}-{int(datetime.now().timestamp()) % 10000}"

            # 移除了 {{< ad300 >}} 短代码的追加，以满足 AdSense 质量合规要求
            chinese_content = chinese_content.strip() + "\n"
            english_content = english_content.strip() + "\n"

            # 1. 写入中文版
            zh_path = os.path.join(output_dir, f"{base_name}.zh.md")
            with open(zh_path, "w", encoding="utf-8") as f:
                f.write(chinese_content)

            # 2. 写入英文版
            en_path = os.path.join(output_dir, f"{base_name}.en.md")
            with open(en_path, "w", encoding="utf-8") as f:
                f.write(english_content)

            print(f"[+] 自动化双语矩阵对齐成功！")
            print(f"    -> 中文节点: {zh_path}")
            print(f"    -> 英文节点: {en_path}")
            
            with open(os.path.join(cwd, "new_posts.txt"), "w", encoding="utf-8") as f:
                f.write(zh_path + "\n")
                f.write(en_path + "\n")

            # ==========================================
            # 第三阶段核心：向 SQLite 数据库汇报战果，完成核销
            # ==========================================
            if task_id:
                db_path = os.path.join(cwd, "..", "roach_matrix.db")
                if os.path.exists(db_path):
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    current_time_db = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # 将状态更新为 published
                    cursor.execute("UPDATE seo_matrix SET status = 'published', published_at = ? WHERE id = ?", (current_time_db, task_id))
                    conn.commit()
                    conn.close()
                    print(f"[+] 任务 ID: {task_id} 已在矩阵中标记为 Published。全链路闭环达成！")
                else:
                    print("[-] 警告：未找到 roach_matrix.db 数据库，状态核销跳过。")
            else:
                print("[-] 警告：本次载荷缺少 task_id，无法进行数据库核销。")

        else:
            print("[-] 异常：大模型未按照规定格式生成语言隔离墙，无法分流落盘。建议检查 Token 是否截断。")
            debug_path = os.path.join(cwd, "failed_payload.txt")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[-] 原始输出已保存至 {debug_path} 以供调试。")

        # [清理] 成功流转后，删除物理层载荷文件
        try:
            if os.path.exists(data_path): os.remove(data_path)
            if os.path.exists(social_data_path): os.remove(social_data_path)
        except Exception as e:
            pass

    except httpx.HTTPStatusError as exc:
        print(f"[-] 算力调度异常：网关返回错误状态码 {exc.response.status_code}")
    except Exception as e:
        print(f"[-] 算力调度异常: {e}")


if __name__ == "__main__":
    process_payload()