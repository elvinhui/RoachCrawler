# ====================================================================
# Infrastructure Operations Automation Router - Windows Pipeline
# ====================================================================
$ErrorActionPreference = "Stop"

Write-Host "[*] ========================================================" -ForegroundColor Cyan
Write-Host "[*]  InfraOps Router Windows 自动化流水线开始点火..." -ForegroundColor Cyan
Write-Host "[*] ========================================================" -ForegroundColor Cyan

# 1. 安全阻断检查
if (-not (Test-Path ".env")) {
    Write-Host "[-] 致命错误：未找到机密金库 .env 文件，拒绝点火！" -ForegroundColor Red
    exit
}

# 2. 阶段一：嗅探
Write-Host "[*] 阶段 1/3: 启动 Serp Sniffer 探测目标网关..." -ForegroundColor Yellow
python scripts/serp_sniffer.py

# 3. 阶段二：大模型洗稿
Write-Host "[*] 阶段 2/3: 调度 DeepSeek 算力重构中英双语载荷..." -ForegroundColor Yellow
$env:HTTP_PROXY=""
$env:HTTPS_PROXY=""
python scripts/coder_agent.py

# 4. 阶段三：GitHub 边缘同步
Write-Host "[*] 阶段 3/3: 打包资产推送到云端..." -ForegroundColor Yellow
git add .
$current_time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
git commit -m "auto: automated content matrix refresh via windows pipeline at $current_time"
git push origin main

Write-Host "[+] ========================================================" -ForegroundColor Green
Write-Host "[+]  流水线全部跑通！Cloudflare Pages 已经开始在全球节点点火上线！" -ForegroundColor Green
Write-Host "[+] ========================================================" -ForegroundColor Green