#!/bin/bash
# ====================================================================
# Infrastructure Operations Automation Router - Full Pipeline Trigger
# ====================================================================

# 开启错误熔断：一旦某一步报错，脚本立刻安全退出，防止带病提交坏包
set -e

echo "[*] ========================================================"
echo "[*]  InfraOps Router 自动化流水线开始点火..."
echo "[*] ========================================================"

# 1. 物理定位工作区根目录
cd "$(dirname "$0")"

# 2. 检查并挂载系统机密金库
if [ ! -f .env ]; then
    echo "[-] 致命错误：未找到机密金库 .env 文件，拒绝点火！"
    exit 1
fi

# 3. 自动激活 Python 局部虚拟环境
if [ -d "venv" ]; then
    echo "[*] 正在激活 Python 虚拟环境..."
    source venv/bin/activate
fi

# 4. 阶段零：趋势词挖掘
echo "[*] 阶段 0/3: 启动 Data Crawler 挖掘最新热词并注入矩阵..."
python scripts/trend_crawler.py || echo "[-] Trend Crawler 异常，跳过挖掘阶段。"

# 4.5 阶段 0.5：全网社交舆情雷达
echo "[*] 阶段 0.5/3: 启动 Social Radar (last30days) 抓取全网真实讨论并生成草稿..."
node scripts/auto_draft.js "Data Center Operations" || echo "[-] Social Radar 异常，跳过草稿生成。"

# 5. 阶段一：公网流量嗅探
echo "[*] 阶段 1/3: 启动 Serp Sniffer，拦截高价值行业动态..."
python scripts/serp_sniffer.py

# 5. 阶段二：算力调度与双语文章生成
echo "[*] 阶段 2/3: 调度 DeepSeek 算力，重构中英双语对称载荷..."
# 强制清空当前终端可能残存的代理幽灵变量，保证直连 DeepSeek API
HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy="" ALL_PROXY="" all_proxy="" python scripts/coder_agent.py

# 6. 阶段三：云端数据中心同步
echo "[*] 阶段 3/3: 打包资产，向云端边缘节点推送全量固件..."
git add .

# 抓取当前物理机时间戳，动态写入提交日志
CURRENT_TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
git commit -m "auto: automated content matrix refresh via pipeline at $CURRENT_TIMESTAMP"

echo "[*] 正在向 GitHub 发送数据包..."
git push origin main

echo "[+] ========================================================"
echo "[+]  流水线全部跑通！云端 Cloudflare Pages 已触发全球 CDN 编译！"
echo "[+] ========================================================"