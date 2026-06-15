const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// 从 serp_sniffer.py 生成的 target_data.txt 中提取任务关键字
const dataPath = path.join(__dirname, 'target_data.txt');
let topic = "Data Center Automation";

if (fs.existsSync(dataPath)) {
  try {
    const payload = JSON.parse(fs.readFileSync(dataPath, 'utf-8'));
    if (payload.target_keyword) {
      topic = payload.target_keyword;
    }
  } catch (e) {
    console.error("[-] 解析 target_data.txt 失败，使用默认关键字", e);
  }
}

console.log(`\n🔍 开始针对主题 "${topic}" 进行全网 30 天舆情抓取...`);
console.log(`这可能需要 1-3 分钟，请耐心等待...\n`);

try {
  // 1. 调用本地整合的 last30days 引擎
  const skillPath = path.join(__dirname, '../.agents/skills/last30days/scripts/last30days.py');
  
  // 使用 python 运行，兼容 GitHub Actions (Linux) 和本地 (Windows)
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
  const output = execSync(`${pythonCmd} "${skillPath}" "${topic}" --auto-resolve --emit=compact`, { 
    encoding: 'utf-8', 
    stdio: ['pipe', 'pipe', 'ignore'] // 忽略 stderr 警告
  });
  
  // 2. 将结果保存到 target_social_data.txt 供 coder_agent.py 读取
  const outPath = path.join(__dirname, 'target_social_data.txt');
  fs.writeFileSync(outPath, output);
  
  console.log(`✅ 抓取完成！社交舆情数据已写入 target_social_data.txt`);
  
} catch (error) {
  console.error("❌ 抓取失败：");
  console.error(error.message);
  if (error.stdout) console.error(error.stdout);
}
