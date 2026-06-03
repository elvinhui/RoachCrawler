# ====================================================================
# Infrastructure Operations Automation Router - Windows Pipeline
# ====================================================================
$ErrorActionPreference = "Stop"

Write-Host "[*] ========================================================" -ForegroundColor Cyan
Write-Host "[*]  InfraOps Router Windows 自动化流水线开始点火..." -ForegroundColor Cyan
Write-Host "[*] ========================================================" -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    Write-Host "[-] 致命错误：未找到机密金库 .env 文件，拒绝点火！" -ForegroundColor Red
    exit
}

# ==========================================
# 动态寻路：智能定位 PyCharm 虚拟 Python 引擎
# ==========================================
$py_engine = "C:\Users\KATANA 17 B13V\AppData\Local\Python\pythoncore-3.14-64\python.exe"
# if (Test-Path "venv\Scripts\python.exe") {
#     $py_engine = ".\venv\Scripts\python.exe"
#     Write-Host "[+] 成功挂载 PyCharm 局部虚拟引擎 (venv)" -ForegroundColor DarkGray
# } elseif (Test-Path ".venv\Scripts\python.exe") {
#     $py_engine = ".\.venv\Scripts\python.exe"
#     Write-Host "[+] 成功挂载局部虚拟引擎 (.venv)" -ForegroundColor DarkGray
# } else {
#     Write-Host "[!] 未检测到局部 venv，尝试调用系统全局 Python..." -ForegroundColor DarkGray
# }

Write-Host "[*] 阶段 1/3: 启动 Serp Sniffer 探测目标网关..." -ForegroundColor Yellow
& $py_engine scripts/serp_sniffer.py

Write-Host "[*] 阶段 2/3: 调度 DeepSeek 算力重构中英双语载荷..." -ForegroundColor Yellow
$env:HTTP_PROXY=""
$env:HTTPS_PROXY=""
& $py_engine scripts/coder_agent.py

Write-Host "[*] 阶段 3/3: 打包资产推送到云端..." -ForegroundColor Yellow
git add .
$current_time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
git commit -m "auto: automated content matrix refresh via windows pipeline at $current_time"
git push origin main

Write-Host "[+] ========================================================" -ForegroundColor Green
Write-Host "[+]  流水线全部跑通！Cloudflare Pages 已经开始在全球节点点火上线！" -ForegroundColor Green
Write-Host "[+] ========================================================" -ForegroundColor Green
