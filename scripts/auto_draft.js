const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// 从命令行获取主题，默认为 Data Center Automation
const topic = process.argv[2] || "Data Center Automation";
console.log(`\n🔍 开始针对主题 "${topic}" 进行全网 30 天舆情抓取...`);
console.log(`这可能需要 1-3 分钟，请耐心等待...\n`);

try {
  // 1. 调用本地整合的 last30days 引擎
  const skillPath = path.join(__dirname, '../.agents/skills/last30days/scripts/last30days.py');
  
  // 使用 py 或 python3 运行，开启 --auto-resolve 和 --emit=compact
  const output = execSync(`py "${skillPath}" "${topic}" --auto-resolve --emit=compact`, { 
    encoding: 'utf-8', 
    stdio: ['pipe', 'pipe', 'ignore'] // 忽略 stderr 警告
  });
  
  // 2. 生成 Hugo 草稿的 Frontmatter
  const date = new Date();
  const timestamp = Math.floor(date.getTime() / 1000);
  const isoDate = date.toISOString();
  
  const frontmatter = `---
title: "Research Log: ${topic} - ${isoDate.split('T')[0]}"
date: ${isoDate}
draft: true
tags: ["Research", "last30days", "Automated"]
categories: ["Automation Ideas"]
---

> **自动生成的调研日志**  
> 这份草稿由 \`last30days\` 脚本自动生成，汇总了全网过去 30 天关于 **${topic}** 的真实讨论和数据。
> 你可以直接让 AI 基于下方的 Raw Data 为你生成一篇带观点的技术文章。

<!--more-->

## Raw Research Dump

`;

  // 3. 将抓取的内容和 Frontmatter 合并
  const content = frontmatter + output;
  const fileName = `research-${timestamp}.md`;
  
  // 4. 写入到 Hugo 内容目录（中英文双语文件夹）
  const zhFilePath = path.join(__dirname, '../site_payload/content/posts', fileName);
  const enFilePath = path.join(__dirname, '../site_payload/content/en/posts', fileName);
  
  fs.writeFileSync(zhFilePath, content);
  fs.writeFileSync(enFilePath, content);
  
  console.log(`✅ 抓取完成！自动草稿已生成：`);
  console.log(`   - 🇨🇳 ${zhFilePath}`);
  console.log(`   - 🇺🇸 ${enFilePath}`);
  console.log(`\n你可以在本地启动 Hugo 并在 drafts 中预览，或者让 AI 帮你根据这份草稿写成正式文章！`);
  
} catch (error) {
  console.error("❌ 抓取失败：");
  console.error(error.message);
  if (error.stdout) console.error(error.stdout);
}
