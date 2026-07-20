# ====================================================================
# Infrastructure Operations Automation Router - Windows Pipeline
# ====================================================================
$ErrorActionPreference = "Stop"
# [关键升级1] 强制 PowerShell 使用 UTF-8，防止 Python 输出的中文字符在终端变成乱码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "[*] ========================================================" -ForegroundColor Cyan
Write-Host "[*]  InfraOps Router Windows 自动化流水线开始点火..." -ForegroundColor Cyan
Write-Host "[*] ========================================================" -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    Write-Host "[-] 致命错误：未找到机密金库 .env 文件，拒绝点火！" -ForegroundColor Red
    exit
}

# [关键升级2] 增加对 SQLite 矩阵中枢的探测
if (-not (Test-Path "roach_matrix.db")) {
    Write-Host "[-] 严重异常：未检测到流量矩阵数据库 roach_matrix.db！" -ForegroundColor Red
    Write-Host "[-] 请先运行 scripts/core_db.py 或 scripts/import_json_to_db.py 注入弹药。" -ForegroundColor Yellow
    exit
}

# ==========================================
# 动态寻路：智能定位 Python 引擎
# ==========================================
$py_engine = "C:\Users\KATANA 17 B13V\AppData\Local\Python\pythoncore-3.14-64\python.exe"

Write-Host "`n[*] 阶段 0/3: 启动 Data Crawler 挖掘最新热词并注入矩阵..." -ForegroundColor Yellow
& $py_engine scripts/trend_crawler.py
if ($LASTEXITCODE -ne 0) { Write-Host "[-] Trend Crawler 异常，跳过挖掘阶段。" -ForegroundColor DarkGray }

Write-Host "`n[*] 阶段 1/3: 启动 Serp Sniffer 探测目标网关 (从 SQLite 矩阵提取指令)..." -ForegroundColor Yellow
& $py_engine scripts/serp_sniffer.py
# 错误熔断：如果探针报错崩溃，立刻停止流水线，不执行后续消耗 Token 的操作
if ($LASTEXITCODE -ne 0) { Write-Host "[-] 探针层执行失败，流水线熔断。" -ForegroundColor Red; exit }

Write-Host "`n[*] 阶段 1.5/3: 启动 Social Radar (last30days) 抓取全网真实讨论..." -ForegroundColor Yellow
node scripts/auto_draft.js
if ($LASTEXITCODE -ne 0) { Write-Host "[-] Social Radar 异常，跳过抓取。" -ForegroundColor DarkGray }

Write-Host "`n[*] 阶段 2/3: 调度 DeepSeek 算力重构中英双语载荷与核销..." -ForegroundColor Yellow
$env:HTTP_PROXY=""
$env:HTTPS_PROXY=""
& $py_engine scripts/coder_agent.py
if ($LASTEXITCODE -ne 0) { Write-Host "[-] 算力层执行失败，流水线熔断。" -ForegroundColor Red; exit }

Write-Host "`n[*] 阶段 2.5/3: 启动 Quality Gate 内容质量扫描..." -ForegroundColor Yellow
& $py_engine scripts/quality_gate.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[-] Quality Gate 检测到不合规内容，触发 AI 自动修复..." -ForegroundColor Yellow
    & $py_engine scripts/auto_fixer.py
    Write-Host "[*] 修复完成，重新执行 Quality Gate..." -ForegroundColor Yellow
    & $py_engine scripts/quality_gate.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[-] 二次检测仍未通过，请手动检查 quarantine/ 目录。流水线继续提交合格内容..." -ForegroundColor Red
    }
}

Write-Host "`n[*] 阶段 2.7/3: 将新增内容推送到云端对象存储 (AWS S3)..." -ForegroundColor Yellow
& $py_engine scripts/upload_to_s3.py
if ($LASTEXITCODE -ne 0) { Write-Host "[-] S3 上传异常，部分内容可能未推送到云端。" -ForegroundColor DarkGray }

Write-Host "`n[*] 阶段 3/3: 打包资产推送到云端..." -ForegroundColor Yellow
git add .

# [关键升级3] 拦截无效推送：如果数据库空了没生成新文章，git commit 会报错中断。所以先判断是否有文件变动。
if (git status --porcelain) {
    $current_time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    git commit -m "auto: automated content matrix refresh via windows pipeline at $current_time"
    git push origin main

    Write-Host "`n[+] ========================================================" -ForegroundColor Green
    Write-Host "[+]  流水线全部跑通！新节点代码已推入仓库！" -ForegroundColor Green
    Write-Host "[+]  Cloudflare Pages 已经开始在全球边缘节点编译上线！" -ForegroundColor Green
    Write-Host "[+] ========================================================" -ForegroundColor Green

    # 7. 阶段四：提交网站地图 (Sitemap)
    # 这就好比给爬虫递交了一份你网站的架构图，告诉它这里有多少个房间（页面），别漏了。
    Write-Host "`n[*] 阶段 4/4: 向搜索引擎主动推送 Sitemap..." -ForegroundColor Yellow
    & $py_engine scripts/submit_sitemap.py
    if ($LASTEXITCODE -ne 0) { Write-Host "[-] Sitemap 推送失败，请检查网络。" -ForegroundColor DarkGray }
} else {
    Write-Host "`n[*] 暂无新资产生成 (可能是任务矩阵已清空)。跳过 Git 推送环节。流水线安全挂起。" -ForegroundColor DarkGray
}