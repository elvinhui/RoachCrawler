---
title: "从零重写 Redis、Git 和数据库：80+ 门硬核课程背后的学习真相与避坑指南"
date: 2026-09-05T01:31:47.485860+00:00
draft: false
description: "深入拆解从零重写 Redis、Git 和数据库的学习方法论。分析 Ship That Code 等 80+ 门硬核课程的价值、学习路径与真实成本，帮你判断这条路是否值得走。"
summary: "从零重写基础设施软件是提升工程能力的最陡峭学习曲线之一。本文结合社区反馈，拆解 Redis、Git 与数据库重写的核心难点、学习顺序与预期收益。"
categories: ["Developer Tools"]
tags: ["Tech", "Analysis"]
cover:
  image: "/images/cover_1788571907_8129.jpg"
  alt: "Developer Tools 技术可视化"
  hiddenInList: false
  hiddenInSingle: false
---

## 核心要点 (Key Takeaways)

- **重写不是抄代码**：真正的价值在于理解 Redis 的内存编码、Git 的 DAG 对象模型和数据库的 B+ 树与事务日志，而不是把源码读一遍。
- **学习顺序有讲究**：社区公认的最优路径是 Redis → Git → 数据库，难度递增，每完成一个都为下一个铺路。
- **时间成本被严重低估**：一个像样的数据库重写项目动辄 200-400 小时，远非周末 hackathon 能搞定。
- **80+ 门课程质量参差**：Ship That Code 这类平台的优势在于体系化，但你必须自己判断哪些项目值得投入。
- **LLM 是双刃剑**：Hacker News 上那篇爆文《How I use LLMs to learn complex topics》讨论的方法论，用在重写项目上能加速，但也可能让你产生"懂了"的错觉。

## 为什么"从零重写"突然成了最火的学习方式？

Hacker News 上有个现象级趋势——过去几个月，大量工程师开始晒自己"从空文件开始"重写 Redis、Git、SQLite 的进度。Ship That Code 这类平台直接把这套玩法产品化了：179 门课程、37 种语言，核心方法论就三个词——**choose → write → run**。

说白了就是：选一个你每天都在用的工具，假装它不存在，从零开始实现一个能跑的版本。

这跟传统的"读源码"学习法有啥本质区别？

读源码是线性叙事，作者帮你把复杂度消化好了，你跟着走就行。但重写是**非线性战斗**——你得自己决定先写哪部分、遇到 bug 怎么排查、性能瓶颈在哪里。Git 的内部存储格式、Redis 的事件循环、数据库的 WAL 日志，这些知识点你读十遍源码都不如自己踩一遍坑记得牢。

Reddit 上 r/SideProject 有个老哥说得挺到位："我花了三年读 Redis 源码，每次读到一半就放弃。后来逼自己重写一个简化版，三周时间比我三年读源码学到的东西都多。"

当然这话有点夸张，但核心观点没错——**动手做的记忆留存率远高于阅读**。

## 拆解三大重写项目：难度、核心知识点、预期时间

### 第一阶段：重写 Redis（约 40-80 小时）

Redis 是绝佳的入门项目，因为它的核心数据结构都在内存里，不需要处理磁盘 I/O 的复杂性。

你要实现的东西其实不多，但每样都得做到位：

1. **内存存储引擎**：哈希表、跳表、动态字符串——别用现成的，得自己实现。
2. **RESP 协议**：Redis 的序列化协议，简单但细节多。`*3\r\n$3\r\nSET\r\n...` 这种格式你得手写解析器。
3. **事件循环**：单线程 + epoll/kqueue 的 I/O 多路复用，这是理解 Redis 高性能的关键。
4. **持久化**：RDB 快照和 AOF 日志，这部分能让你理解"为什么 Redis 重启不丢数据"。

真正的难点在第 3 和第 4 个。事件循环看起来简单，但你要处理半包、粘包、定时器、信号处理，各种边缘情况能把人逼疯。AOF 日志更是如此——追加写、fsync 策略、日志重写，每一步都有坑。

去年有个哥们儿在 HN 上分享他的 Redis 重写经历，他卡在 AOF 重写那里整整四天，就是因为没处理好在重写过程中新写入的命令。这个问题 Redis 官方用"子进程 + 写时复制"解决，你自己实现的时候大概率会想出一个更笨但能跑的方案——**这就够了**。

### 第二阶段：重写 Git（约 60-120 小时）

Git 的难度比 Redis 上了一个台阶，因为它的核心是**内容寻址的文件系统**。

你需要理解并实现：

1. **对象存储**：blob、tree、commit、tag 四种对象类型，用 SHA-1 哈希做地址。
2. **.git 目录结构**：objects/、refs/、HEAD、index 文件。
3. **索引（index）**：这个最容易被忽略，但它是 Git 性能的核心——一个二进制格式的暂存区文件。
4. **分支与合并**：三路合并算法、冲突检测。

Git 重写最反直觉的地方在于——你写的每个命令（add、commit、branch）本质上都是在**操作一个有向无环图（DAG）**。commit 对象指向 tree 对象和父 commit，branch 只是一个指向 commit 的指针。

理解了这一点，很多之前觉得玄学的问题就豁然开朗了。比如为什么 Git 分支切换那么快？因为它只是在移动指针。为什么 cherry-pick 会产生新的 commit？因为它在 DAG 上创建了一个新节点。

但真正折磨人的是索引文件格式。Git 的 index 文件有固定的二进制布局——12 字节的头部、按路径排序的条目、扩展区域、SHA-1 校验和。你得逐字节地解析它，任何偏移量错误都会导致"index file corrupt"错误。

这里有个真实案例：Stack Overflow 上有个问题被问了无数次——"为什么我的 Git index 文件损坏了？"答案通常是文件权限问题或者磁盘写满。但你自己实现一遍索引解析器之后，就会真正理解为什么 Git 在 index 文件末尾放了一个 20 字节的 SHA-1 校验和——它能帮你检测出文件是否被截断或篡改。

### 第三阶段：重写数据库（约 200-400 小时）

这是终极 Boss。一个最小可用的关系型数据库需要：

1. **存储引擎**：B+ 树或者 LSM 树——这是数据持久化的核心。
2. **事务与 WAL**：预写日志、原子性、隔离性——ACID 的底层实现。
3. **SQL 解析器**：词法分析、语法分析、生成抽象语法树。
4. **查询优化器**：简单起见可以先不写，但至少要懂为什么 order of JOINs 会影响性能。

B+ 树本身就是一个可怕的项目。你要处理节点分裂、合并、叶节点链表、缓存淘汰策略——每个环节都有无数细节。网上有个经典的"500 行代码实现数据库"教程，但那个只实现了 append-only 的存储，连 UPDATE 都做不到。

WAL 更是魔鬼细节。你要保证：写入 WAL 的日志在崩溃恢复时能完整重放，但不能重复应用。这涉及到 LSN（日志序列号）和页面的脏标记——自己实现一遍才能真正理解为什么数据库需要 fsync，以及 fsync 为什么这么慢。

数据库项目做完一个能跑的版本，你再看 PostgreSQL 的源码，很多之前看不懂的东西会突然变得清晰——因为你已经知道了"正确的做法是什么"，现在只是在看"工业级的做法有多精致"。

## 从零重写 Redis、Git、数据库的完整技术路径

### 第一步：搭建项目骨架（0.5 天）

不管是哪个项目，都建议用 Rust 或者 Go。理由很简单：内存安全和并发支持好，能让你专注于业务逻辑而不是段错误。

```bash
# 以 Rust 为例
cargo new my-redis --name myredis
cd my-redis

# 目录结构按模块划分
mkdir -p src/{protocol,store,eventloop,persistence}
```

### 第二步：实现协议层（1-2 天）

以 Redis 为例，第一步是实现 RESP 协议解析器：

```rust
// src/protocol/resp.rs
// 一个极简的 RESP 解析器框架

pub enum RespValue {
    SimpleString(String),
    Error(String),
    Integer(i64),
    BulkString(Option<String>),  // None 表示 null
    Array(Vec<RespValue>),
}

pub fn parse_resp(input: &[u8]) -> Result<(RespValue, usize), String> {
    // 第一个字节决定类型
    match input[0] {
        b'+' => {
            // 读到 \r\n 为止
            let end = input.iter().position(|&b| b == b'\n')
                .ok_or("未终止的字符串")?;
            let s = String::from_utf8_lossy(&input[1..end - 1]).to_string();
            Ok((RespValue::SimpleString(s), end + 1))
        }
        b'$' => {
            // 先读长度，再读内容
            // 注意：长度后面跟 \r\n，内容后面也跟 \r\n
            // 这部分最容易出错
            todo!("实现 BulkString 解析")
        }
        b'*' => {
            // 读数组长度，然后逐个解析元素
            todo!("实现 Array 解析")
        }
        _ => Err(format!("未知类型: {}", input[0] as char)),
    }
}
```

这里最容易出错的点是边界情况——比如 `BulkString` 的长度为 -1 表示 null，空字符串 `$0\r\n\r\n` 跟 null 完全不同。这些细节你在文档里看到不会觉得有什么，但写测试的时候会被反复折磨。

### 第三步：核心存储引擎（3-5 天）

不需要一上来就实现跳表，先用一个简单的 `HashMap` 跑通全链路，后续再优化：

```rust
// src/store/mod.rs
use std::collections::HashMap;

pub struct Store {
    data: HashMap<String, StoreValue>,
}

pub struct StoreValue {
    pub value: Vec<u8>,
    pub expires_at: Option<u128>,  // 毫秒时间戳
}

impl Store {
    pub fn new() -> Self {
        Self {
            data: HashMap::new(),
        }
    }

    pub fn set(&mut self, key: String, value: Vec<u8>, ttl_ms: Option<u128>) {
        let expires_at = ttl_ms.map(|ttl| {
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_millis() + ttl
        });
        self.data.insert(key, StoreValue { value, expires_at });
    }

    pub fn get(&self, key: &str) -> Option<&Vec<u8>> {
        // 注意：惰性过期——在读取时检查是否过期
        // 这也是 Redis 的默认策略之一
        match self.data.get(key) {
            Some(v) => {
                if let Some(expires_at) = v.expires_at {
                    let now = std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap()
                        .as_millis();
                    if now > expires_at {
                        return None;
                    }
                }
                Some(&v.value)
            }
            None => None,
        }
    }
}
```

这里有个面试必问的知识点：**Redis 的过期删除策略是惰性删除 + 定期删除**。惰性删除就是上面代码里的做法——读取时检查。定期删除则是后台线程每隔一段时间随机抽几个 key 检查过期。你要理解为什么不能只用惰性删除——因为有些 key 永远不会被读取，就会一直占着内存。

### 第四步：事件循环（2-3 天）

这是最考验功力的一部分。Redis 是单线程的，但能支撑 10 万+ QPS，核心就是 epoll。

```rust
// 伪代码展示核心逻辑
// 真正的实现需要用到 mio 或 tokio 等库

loop {
    // 1. 等待事件就绪（最多阻塞 100ms）
    let events = epoll_wait(epoll_fd, timeout_ms=100)?;
    
    // 2. 处理定时器任务（比如过期 key 清理）
    process_timers();
    
    // 3. 遍历就绪的事件
    for event in events {
        if event.is_readable() {
            // 读取客户端请求
            let data = client.read()?;
            // 解析 RESP 命令
            let cmd = parse_resp(&data)?;
            // 执行命令
            let result = execute(cmd)?;
            // 写回响应
            client.write(result)?;
        }
    }
}
```

这里有个关键点：**Redis 的命令执行是原子的**，因为它是单线程的，不需要加锁。但这也意味着你不能在命令处理函数里做任何阻塞操作——比如磁盘 I/O。AOF 的 fsync 策略之所以有 `everysec` 选项，就是为了避免每条命令都阻塞主线程。

### 第五步：持久化（2-3 天）

AOF（Append Only File）是理解 Redis 数据可靠性的关键。核心逻辑：

```rust
// 伪代码：AOF 写入流程
fn handle_write_command(cmd: Command) {
    // 1. 执行内存操作
    store.apply(&cmd);
    
    // 2. 追加到 AOF 缓冲区
    aof_buffer.append(serialize(cmd));
    
    // 3. 根据 fsync 策略决定是否刷盘
    match config.aof_fsync_policy {
        FsyncPolicy::Always => {
            // 每条命令都 fsync —— 最安全但最慢
            aof_file.sync_all()?;
        }
        FsyncPolicy::EverySec => {
            // 每秒同步一次 —— 最多丢 1 秒数据
            // 由后台线程执行 fsync
        }
        FsyncPolicy::No => {
            // 交给操作系统决定 —— 可能丢大量数据
        }
    }
}
```

很多人在这一步会问：为什么不直接改文件而要追加日志？答案是——**顺序写比随机写快几个数量级**。追加日志是顺序写，而修改数据文件是随机写。这就是 AOF 和 RDB 背后的核心取舍。

## 学习效率对比：手写 vs 读源码 vs LLM 辅助

最近 Hacker News 上有篇爆文《How I use LLMs to learn complex topics》，548 条评论吵翻了天。有人觉得 LLM 能当无限耐心的导师，也有人觉得它给的代码会让人产生虚假的掌控感。

我的观点是——**LLM 对重写项目的帮助分阶段**：

| 学习方式 | 上手速度 | 理解深度 | 踩坑次数 | 适合阶段 | 时间成本 |
|---------|---------|---------|---------|---------|---------|
| 纯读源码 | 慢（2-3周热身） | 中（容易被细节淹没） | 少 | 已有基础，想深入 | 高（100+小时） |
| 纯手写 | 快（当天能跑） | 高（每个坑都刻骨铭心） | 极多 | 有耐心的人 | 极高（200-400小时） |
| LLM 辅助手写 | 快（1天热身） | 中高（取决于提问质量） | 中 | 想快速验证想法 | 中（80-150小时） |
| 视频课程跟做 | 最快（2小时上手） | 低（容易变成抄代码） | 少 | 完全零基础 | 低（但效果差） |

用 LLM 的正确姿势是让它**解释概念和帮你 debug**，而不是让它替你写核心代码。

比如你卡在 B+ 树节点分裂的逻辑上，你可以问："我的 B+ 树在插入第 4 个键时节点分裂不正确，这是我的代码和测试结果，能帮我看看分裂逻辑哪里出了问题吗？"——这比问"帮我写一个 B+ 树"有价值得多。

Reddit 上 r/learnprogramming 有个帖子总结得精辟：**LLM 让你从"不知道哪里不懂"变成"知道自己哪里不懂"**。它确实能加速学习，但前提是你得能问出好问题。

## 这套学习路径值不值？

时间成本摆在这里——Redis 40-80 小时，Git 60-120 小时，数据库 200-400 小时，全套下来 300-600 小时。对大多数人来说，这是一个巨大的承诺。

但收益是**可迁移的**。你重写完 Redis，理解了事件循环和内存管理，之后学 Nginx、Node.js、甚至是 Kafka 的架构都会快很多。你重写完 Git，理解了 DAG 和内容寻址，再去看区块链、IPFS 这些系统会恍然大悟。你重写完数据库，理解了 B+ 树和 WAL，之后调优 PostgreSQL 或者选型 NoSQL 时，判断力完全不在一个层级。

不过我也得泼盆冷水——**不是每个人都适合这种学习方式**。如果你需要的是快速上手一个框架去干活，那花 300 小时重写数据库就是浪费时间。这套方法适合的是那些想突破瓶颈的资深工程师，而不是刚入行的新人。

最后，一个在 HN 上获得高赞的建议：**不要一个人闷头写**。找个朋友一起，或者至少每完成一个里程碑就发到网上。有人围观和反馈的项目，完成率比独自搞的高出好几倍。Ship That Code 这类平台之所以有社区功能，也正是因为这个原因。

## 常见问题 (FAQ)

### Q: 重写 Redis/Git/数据库需要什么前置知识？

你需要扎实掌握一门系统级语言（C、Rust、Go 都行），理解基本的数据结构（哈希表、树），以及基础的网络编程知识（socket、TCP）。数据库项目还需要理解磁盘 I/O 和文件系统的基本原理。如果你还不太会这些，建议先做一些小的命令行工具项目热身。

### Q: 完成重写项目后，面试时怎么说？

这可能是最大的误区——面试官并不关心你写的代码有多少行，而是关心你**为什么做这些设计决策**。比如"为什么 AOF 的 fsync 策略要分为三种？"、"为什么 Git 的 commit 要同时指向 tree 和 parent？"能解释清楚这些取舍，比展示代码库更有说服力。很多工程师靠一个数据库重写项目拿到了存储部门的 offer。

### Q: LLM 辅助学习和纯手写的效果差距有多大？

差距取决于你问问题的深度。如果你只是让 LLM 帮你生成代码，效果会大打折扣——因为你绕过了最关键的挣扎过程。但如果你把 LLM 当成一个"随时在线的导师"，在卡住时请教原理、在 debug 时请求分析，效果可以接近纯手写。关键在于你要主动控制学习节奏，而不是被动接受代码。

### Q: 3 个项目中应该先做哪一个？

毫无悬念：先 Redis。原因有三个——代码量最少（一个周末能跑通核心功能）、不涉及磁盘 I/O（降低复杂度）、社区资料最丰富（遇到问题容易搜到答案）。做完 Redis 之后你对事件驱动架构有了体感，再做 Git 时会更从容。

## References & Community Insights

这一波学习潮流的几个关键讨论节点：

- Ship That Code 的课程页面—— https://shipthatcode.com/ ——180+ 门课程，从 Redis 到编译器到容器运行时，范围确实广。
- 《Build Your Own Redis》一书的完成公告—— https://build-your-own.org/redis/ ——作者把整本书免费放到网上，从零带你用 C 语言重写 Redis，质量非常硬。
- Hacker News 上《How I use LLMs to learn complex topics》的讨论（835 分 / 548 评论）—— https://news.yaml.com/ 这篇文章的作者用 LLM 作为学习伙伴来理解复杂系统，评论区对"LLM 是否会摧毁深度学习"的争论很有意思。
- 一个在 HN 上长期置顶的合集页—— https://github.com/codecrafters-io/build-your-own-x ——汇总了各种从零重写项目的教程链接，从数据库到操作系统到神经网络都有，社区维护很活跃。
- Redis 官方代码库—— https://github.com/redis/redis ——如果你想对照你的实现和官方的差异，这是最好的参考。但建议至少完成核心功能后再看，否则容易被细节淹没。

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "重写 Redis/Git/数据库需要什么前置知识？",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "需要扎实掌握一门系统级语言（C、Rust、Go），理解基本的数据结构（哈希表、树），以及基础的网络编程知识（socket、TCP）。数据库项目还需要理解磁盘 I/O 和文件系统的基本原理。"
    }
  }, {
    "@type": "Question",
    "name": "完成重写项目后，面试时怎么说？",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "面试官关心的是你为什么做这些设计决策，而不是代码量。例如：为什么 AOF 的 fsync 策略分三种？为什么 Git 的 commit 同时指向 tree 和 parent？能解释清楚取舍，比展示代码库更有说服力。"
    }
  }, {
    "@type": "Question",
    "name": "LLM 辅助学习和纯手写的效果差距有多大？",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "差距取决于提问深度。如果只是让 LLM 生成代码，效果会大打折扣。如果把它当成随时在线的导师，在卡住时请教原理、在 debug 时请求分析，效果可以接近纯手写。关键是要主动控制学习节奏。"
    }
  }, {
    "@type": "Question",
    "name": "3 个项目中应该先做哪一个？",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "先做 Redis。代码量最少、不涉及磁盘 I/O、社区资料最丰富。做完 Redis 后对事件驱动架构有了体感，再做 Git 时会更从容。"
    }
  }]
}
</script>

---
✅ All agents reported back!
├─ 🟠 Reddit: 12 threads
├─ 🟡 HN: 12 storys │ 1,593 points │ 1,329 comments
└─ 🗣️ Top voices: r/SillyTavernAI, r/SideProject, r/ArtificialInteligence
---
