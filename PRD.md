# 产品需求文档 (PRD)：自动化 IT 基础设施 SEO 变现平台

## 1. 产品概述 (Product Overview)
本项目旨在构建一个端到端的自动化内容流水线。系统通过定向抓取 IT 基础设施领域（服务器、数据中心运维、网络排错等）的长尾关键词与真实求助帖，调用 DeepSeek API 生成结构化的高质量技术文章，并利用 Hugo 静态框架自动编译部署至前端云平台（如 Vercel）。最终通过精准的自然搜索流量（SEO）接入 Google AdSense 实现被动变现。

## 2. 商业目标与成功指标 (Objectives & OKRs)
**核心目标：** 实现从“选题挖掘 -> 内容生成 -> 网站发布”的全流程零人工干预，并顺利开通 Google AdSense。

**阶段性成功指标：**
*   **Phase 1 (基础设施搭建)：** 跑通本地 Python 脚本至 Vercel 的自动化部署链路，解决 404 错误，实现内容上云。
*   **Phase 2 (冷启动与收录)：** 每日自动化产出 5-10 篇长尾词文章，实现 Google Search Console (GSC) 页面有效收录率大于 70%。
*   **Phase 3 (商业化测试)：** 网站日均独立访客 (UV) 稳定突破 100，成功通过 Google AdSense 审核并产生首笔广告收入。

## 3. 核心受众与内容矩阵 (Target Audience & Content Matrix)
精准定位高净值、强搜索意图的专业技术人群，以获取高 CPC 的广告匹配。

| 分类目录 (Category) | 目标受众 | 内容产出方向 |
| :--- | :--- | :--- |
| **Server Operations** | NOC 工程师、系统管理员 | 戴尔 PowerEdge 硬件告警排查、iDRAC 配置指南、Redfish API 自动化脚本文档。 |
| **Network & Config** | CCNA 备考者、网络工程师 | 思科/Quanta 交换机 CLI 命令行实例、VLAN 排错、OSPF 路由配置报错解决。 |
| **Data Center Guide** | IT 新手、设施运维专员 | 冷热通道气流规划、PDU 负载计算基础、机房硬件标准化巡检 (SOP) 流程。 |

## 4. 核心功能需求 (Functional Requirements)

### 4.1 数据源与关键词挖掘模块 (Data Crawler & Trend Analyzer)
**需求描述：**
通过 Python 自动化脚本，双管齐下挖掘内容主题。主链路接入 Google Trends 获取实时飙升搜索词，辅链路监控垂直技术论坛。筛选出“高搜索增量 + 低竞争度”的 IT 基础设施长尾词。

**技术实现依赖：**
Python 原生生态（推荐使用 `pytrends` 库模拟非官方 API 交互，结合 `BeautifulSoup` 处理论坛 HTML 内容）。

**执行逻辑设计：**

1.  **建立“种子词库” (Seed Matrix)：**
    *   在系统底层预设与机房运维、硬件网络紧密相关的核心基础词。
    *   **示例：** Dell PowerEdge, Redfish API, iDRAC 9, Cisco CCNA, VLAN config, Data Center HVAC。

2.  **趋势自动拉取 (Trends Fetching)：**
    *   脚本每天定时唤醒，遍历种子词库。
    *   通过 `pytrends.related_queries()` 抓取过去 30 天或 7 天内的 “飙升搜索词 (Rising/Breakout)”。
    *   **场景举例：** 预设词是 Dell PowerEdge，Google Trends 返回飙升词 *PowerEdge R760 amber light blinking*（R760 琥珀色指示灯闪烁）。这就成为了一个极佳的文章标题。

3.  **论坛交叉验证 (Forum Cross-Validation) [增强机制]：**
    *   提取 Google Trends 发现的飙升词后，脚本自动在特定的垂直技术论坛（监控目标：Reddit 的 r/homelab, r/ccna 子版块、Spiceworks 等）或 Stack Overflow 进行站内搜索。
    *   **筛选规则：** 如果该词对应着大量的用户提问（标题包含 How to、Error、Failed、vs 的帖子优先抓取）且没有完美的官方解答，该关键词的优先级自动标记为 P0（最高级）。

4.  **清洗与队列输出 (Data Cleaning & Queue)：**
    *   剔除纯品牌词或无明确意图的单字词（如纯粹的 Cisco）。
    *   过滤出带有明确意图的修饰词前缀/后缀（如 how to, error code, vs, tutorial）。
    *   提取原始问题作为文章的主题种子 (Topic Seed)。
    *   最终将合格的精准长尾词列表推送到下游的 DeepSeek API 生成队列中。

### 4.2 AI 智能生成模块 (DeepSeek Engine)
**需求描述：**
将主题种子转化为符合 Hugo 规范且高度 SEO 优化的 Markdown 格式文章。

**执行逻辑：**
调用 DeepSeek API，注入系统设定的 Prompt。

*   **强制输出规范 1 (前端适配)：** 必须在文件顶部输出完美的 YAML Frontmatter（包含 title, date, categories, tags, draft: false），冒号后必须带有空格。
*   **强制输出规范 2 (SEO 增强)：** 文章必须包含清晰的 H2/H3 标题体系，包含至少一个 Markdown 表格（用于对比），并在涉及操作时使用代码块（展示 CLI 命令或 Python 脚本）。

### 4.3 自动化构建与部署模块 (CI/CD Pipeline)
**需求描述：**
实现新文章的自动化上云与渲染。

**执行逻辑：**
1.  Python 脚本每日定时将生成的 `.md` 文件写入本地 Hugo 项目的 `content/posts/` 目录。
2.  脚本自动执行 Git 提交并推送到 GitHub (`git add . -> git commit -> git push`)。
3.  GitHub 仓库的变动自动触发 Vercel 的 Webhook，执行 `hugo --gc --minify` 构建命令，输出并部署 public 文件夹的内容。

## 5. 非功能需求 (Non-Functional Requirements)
*   **成本控制：** 维持极低运营成本。后端依赖 Python 本地或免费云函数运行，网页前端依赖 Vercel 免费额度，存储依赖 GitHub。唯一成本为域名和极少的 API token 费用。
*   **性能与体验：** 网页必须满足 Google 核心网页生命力 (Core Web Vitals) 指标。禁用臃肿的 JS 插件，确保移动端首屏加载时间小于 1.5 秒。
*   **防风控策略：** 避免被 Google 判定为“低质量 AI 内容机器”。脚本需控制每日发布频率（切忌一天发上千篇），发布时间需加入随机化处理。
