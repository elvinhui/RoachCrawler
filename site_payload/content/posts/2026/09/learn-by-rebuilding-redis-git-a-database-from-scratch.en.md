---
title: "Rebuilding Redis, Git, and a Database from Scratch: The 600-Hour Engineering Gauntlet That Actually Works"
date: 2026-09-05T01:31:47.485860+00:00
draft: false
description: "Deep dive into learning by rebuilding Redis, Git, and a database from scratch. Analyze 80+ courses, real time costs, LLM-assisted learning pitfalls, and the optimal build order."
summary: "Rebuilding infrastructure software from scratch is the steepest learning curve in engineering. This guide breaks down the real difficulty of Redis, Git, and database rebuilds, the optimal order, and how to use LLMs without fooling yourself."
categories: ["Developer Tools"]
tags: ["Tech", "Analysis"]
cover:
  image: "/images/cover_1788571907_8129.jpg"
  alt: "Developer Tools Visualization"
  hiddenInList: false
  hiddenInSingle: false
---

## Key Takeaways

- **Rebuilding is not about the code** — it's about internalizing why Redis uses single-threaded event loops, why Git models everything as a DAG of immutable objects, and why databases need WAL before they touch data pages.
- **The community consensus build order is Redis → Git → Database**, with difficulty and time commitment escalating at each stage.
- **Time estimates are brutally underestimated** — a respectable database rebuild runs 200-400 hours. This is not a weekend side project.
- **The "80+ courses" landscape is uneven** — Ship That Code and similar platforms offer structure, but you must decide which projects deserve your time. Many are filler.
- **LLMs accelerate but can deceive** — the viral HN post "How I use LLMs to learn complex topics" (835 points, 548 comments) sparked a debate about whether AI-assisted building creates genuine understanding or just polished surface-level familiarity.

## Why "From-Scratch Rebuilding" Suddenly Became the Hottest Learning Method

Hacker News has been flooded with engineers showing off their progress rebuilding Redis, Git, and SQLite — starting from literally an empty file. Platforms like Ship That Code productized this exact approach: 179 courses across 37 languages, built on one methodology — **choose → write → run**.

Pick a tool you use daily. Pretend it doesn't exist. Rebuild it from zero.

How is this fundamentally different from the classic "read the source code" approach?

Reading source code is a linear narrative. The original author already digested the complexity for you — you just follow along. Rebuilding is **nonlinear warfare**. You decide what to build first, debug your own mistakes, and hit performance bottlenecks with zero guardrails. The event loop in Redis, Git's object storage format, the WAL in a database — you can read about these ten times and still not internalize them. You'll remember them after wrestling with your own broken implementation for three days.

There's a great quote from a thread in r/SideProject: "I spent three years reading Redis source code and gave up every time. Then I forced myself to rebuild a simplified version — I learned more in three weeks than in three years of reading."

That's hyperbolic, but the core point holds: **the retention rate of hands-on building crushes passive reading.**

## Deconstructing the Three Rebuild Projects

### Stage 1: Rebuild Redis (~40-80 hours)

Redis is the perfect entry point because all core data structures live in memory — no disk I/O complexity to deal with yet.

What you actually need to implement:

1. **In-memory storage engine**: hash tables, skip lists, dynamic strings — no using the standard library's implementations.
2. **RESP protocol**: Redis's serialization format. Simple but full of edge cases. You'll hand-write a parser for `*3\r\n$3\r\nSET\r\n...`.
3. **Event loop**: single-threaded + epoll/kqueue I/O multiplexing. This is the key to understanding Redis's high performance.
4. **Persistence**: RDB snapshots and AOF logs. This is where you understand why Redis doesn't lose data on restart.

The real difficulty lives in #3 and #4. The event loop looks simple until you handle partial packets, packet coalescing, timers, and signal handling. AOF is even worse — append-only writes, fsync policies, log rewriting. Every step has a trap.

One developer shared his Redis rebuild story on HN — he was stuck on AOF rewriting for four straight days, all because he didn't handle commands arriving during the rewrite process. The official Redis solution uses "fork + copy-on-write." Your solution will be clunkier, but it will work — **and that's the point**.

### Stage 2: Rebuild Git (~60-120 hours)

Git is a step up because its core is a **content-addressable file system**.

You need to understand and implement:

1. **Object storage**: blob, tree, commit, tag — four object types addressed by SHA-1 hash.
2. **.git directory structure**: objects/, refs/, HEAD, index file.
3. **The index file**: the most overlooked piece, and the key to Git's performance — a binary-format staging area.
4. **Branching and merging**: three-way merge algorithms, conflict detection.

The most counterintuitive part of rebuilding Git: every command you write (add, commit, branch) is fundamentally **manipulating a directed acyclic graph (DAG)**. Commit objects point to tree objects and parent commits. Branches are just pointers to commits.

Once this clicks, so many things that seemed mystical become obvious. Why is branch switching so fast? Because it's just moving a pointer. Why does cherry-pick create a new commit? Because it creates a new node in the DAG.

The thing that will genuinely torture you is the index file format. Git's index has a fixed binary layout — 12-byte header, entries sorted by path, extension regions, and a SHA-1 checksum at the end. You'll parse it byte by byte. Any offset error produces a dreaded "index file corrupt" error.

Real-world relevance: there's a classic Stack Overflow question asked thousands of times — "Why is my Git index file corrupted?" The usual answers are file permission issues or a full disk. But after implementing your own index parser, you'll truly understand why Git puts that 20-byte SHA-1 checksum at the end — it detects truncated or tampered files.

### Stage 3: Rebuild a Database (~200-400 hours)

The final boss. A minimal viable relational database requires:

1. **Storage engine**: B+ tree or LSM tree — the core of data persistence.
2. **Transactions and WAL**: pre-write logging, atomicity, isolation — the underlying implementation of ACID.
3. **SQL parser**: lexical analysis, syntax analysis, AST generation.
4. **Query optimizer**: you can skip this initially, but you need to understand why JOIN order affects performance.

A B+ tree alone is a terrifying project. You'll deal with node splits, merges, leaf-node linked lists, cache eviction policies — each with countless details. There's a famous "500 lines of code database" tutorial online, but it only implements append-only storage. It can't even do UPDATE.

WAL is pure demonic detail. You must guarantee: all log entries written to the WAL can be fully replayed after a crash, but never applied twice. This involves LSN (log sequence numbers) and page dirty markers — implementing this yourself is the only way to truly understand why databases require fsync, and why fsync is so damn slow.

Once you finish a working database, reading PostgreSQL source code becomes a completely different experience — you already know "what the right approach is," now you're just studying "how industrial-grade does it."

## The Concrete Build Path: Step-by-Step

### Step 1: Scaffold the project (half a day)

Rust or Go is the right choice regardless of which project you pick. Memory safety and good concurrency support let you focus on business logic instead of segfaults.

```bash
# Rust example
cargo new my-redis --name myredis
cd my-redis

# Organize modules by responsibility
mkdir -p src/{protocol,store,eventloop,persistence}
```

### Step 2: Implement the protocol layer (1-2 days)

Using Redis as the example, the first step is the RESP parser:

```rust
// src/protocol/resp.rs
// A minimal RESP parser skeleton

pub enum RespValue {
    SimpleString(String),
    Error(String),
    Integer(i64),
    BulkString(Option<String>),  // None represents null
    Array(Vec<RespValue>),
}

pub fn parse_resp(input: &[u8]) -> Result<(RespValue, usize), String> {
    // First byte determines the type
    match input[0] {
        b'+' => {
            // Read until \r\n
            let end = input.iter().position(|&b| b == b'\n')
                .ok_or("Unterminated string")?;
            let s = String::from_utf8_lossy(&input[1..end - 1]).to_string();
            Ok((RespValue::SimpleString(s), end + 1))
        }
        b'$' => {
            // Read the length first, then the content
            // Note: length is followed by \r\n, content is also followed by \r\n
            // This is where bugs love to hide
            todo!("Implement BulkString parsing")
        }
        b'*' => {
            // Read array length, then parse each element
            todo!("Implement Array parsing")
        }
        _ => Err(format!("Unknown type: {}", input[0] as char)),
    }
}
```

The edge cases here are brutal. A `BulkString` with length -1 means null. An empty string `$0\r\n\r\n` is completely different from null. These details seem trivial in documentation, but writing tests will torment you.

### Step 3: Core storage engine (3-5 days)

Don't implement a skip list on day one. Start with a simple `HashMap` to get the full pipeline working, then optimize:

```rust
// src/store/mod.rs
use std::collections::HashMap;

pub struct Store {
    data: HashMap<String, StoreValue>,
}

pub struct StoreValue {
    pub value: Vec<u8>,
    pub expires_at: Option<u128>,  // epoch milliseconds
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
        // Note: lazy expiration — check expiry on read
        // This is also one of Redis's default strategies
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

Here's a classic interview question hiding in this code: **Redis's expired-key deletion strategy is lazy deletion + periodic deletion**. Lazy deletion is what the code above does — check on read. Periodic deletion means a background thread samples a few keys at intervals and checks expiry. You need to understand why lazy deletion alone is insufficient — some keys will never be read and will consume memory forever.

### Step 4: Event loop (2-3 days)

This is the part that tests your engineering maturity. Redis is single-threaded yet handles 100k+ QPS. The core is epoll.

```rust
// Pseudocode showing the core logic
// A real implementation needs mio or tokio

loop {
    // 1. Wait for events (block for at most 100ms)
    let events = epoll_wait(epoll_fd, timeout_ms=100)?;
    
    // 2. Process timer tasks (e.g., expired key cleanup)
    process_timers();
    
    // 3. Iterate over ready events
    for event in events {
        if event.is_readable() {
            // Read the client request
            let data = client.read()?;
            // Parse the RESP command
            let cmd = parse_resp(&data)?;
            // Execute the command
            let result = execute(cmd)?;
            // Write the response
            client.write(result)?;
        }
    }
}
```

Critical insight: **Redis command execution is atomic because it's single-threaded — no locks required.** But this also means you cannot do any blocking operations in the command handler — like disk I/O. That's precisely why the AOF fsync policy has an `everysec` option — to avoid blocking the main thread with every single command.

### Step 5: Persistence (2-3 days)

AOF (Append Only File) is the key to understanding Redis's data durability. Core logic:

```rust
// Pseudocode: AOF write flow
fn handle_write_command(cmd: Command) {
    // 1. Execute in-memory operation
    store.apply(&cmd);
    
    // 2. Append to AOF buffer
    aof_buffer.append(serialize(cmd));
    
    // 3. Decide whether to flush based on fsync policy
    match config.aof_fsync_policy {
        FsyncPolicy::Always => {
            // fsync every command — safest but slowest
            aof_file.sync_all()?;
        }
        FsyncPolicy::EverySec => {
            // Sync once per second — lose at most 1 second of data
            // Executed by a background thread
        }
        FsyncPolicy::No => {
            // Let the OS decide — can lose a lot of data
        }
    }
}
```

People ask: why append to a log instead of modifying the data file directly? The answer: **sequential writes are orders of magnitude faster than random writes.** Appending to a log is sequential. Modifying a data file is random. That's the core tradeoff between AOF and RDB.

## Learning Efficiency: Hand-Writing vs Reading Source vs LLM-Assisted

A viral HN post recently — "How I use LLMs to learn complex topics" — triggered 548 comments of heated debate. Some see LLMs as infinitely patient tutors. Others argue the code LLMs produce creates an illusion of competence.

My take: **the value of LLMs in rebuild projects varies by stage**:

| Learning Method | Time to First Run | Depth of Understanding | Bugs Encountered | Best For | Total Time Cost |
|---|---|---|---|---|---|
| Pure source reading | Slow (2-3 weeks warm-up) | Medium (easy to drown in details) | Few | Those with foundation | High (100+ hours) |
| Pure hand-writing | Fast (running same day) | High (every bug is unforgettable) | Many | Patient people | Very high (200-400 hours) |
| LLM-assisted hand-writing | Fast (1 day warm-up) | Medium-high (depends on question quality) | Medium | Validating ideas quickly | Medium (80-150 hours) |
| Video course following | Fastest (2 hours to start) | Low (becomes copy-paste) | Few | Complete beginners | Low (but poor results) |

The right way to use LLMs is to have them **explain concepts and help you debug** — not write core code for you.

If you're stuck on B+ tree node split logic, ask: "My B+ tree splits incorrectly when inserting a 4th key. Here's my code and test output — can you spot the bug in the split logic?" — That's infinitely more valuable than asking "write me a B+ tree."

A concise summary from a r/learnprogramming thread: **LLMs take you from "I don't know what I don't know" to "I know exactly what I don't know."** They do accelerate learning, but only if you can ask good questions.

## Is This Learning Path Worth It?

The time cost is real — Redis at 40-80 hours, Git at 60-120, Database at 200-400. The full gauntlet runs 300-600 hours. For most people, that's a massive commitment.

But the payoff is **transferable**. Rebuild Redis and understand event loops and memory management — Nginx, Node.js, even Kafka's architecture become faster to learn. Rebuild Git and understand DAGs and content addressing — blockchain and IPFS suddenly make sense. Rebuild a database and understand B+ trees and WAL — your judgment when tuning PostgreSQL or choosing a NoSQL database operates on a completely different level.

Now for the cold water: **this isn't for everyone**. If you need to ship a feature with a framework by next week, spending 300 hours rebuilding a database is pure waste. This path is for senior engineers hitting a plateau, not newcomers trying to land their first job.

One piece of advice from a heavily upvoted HN comment: **don't build alone in a vacuum**. Find a friend to do it with, or at minimum post your progress publicly after each milestone. Projects with an audience and feedback loop have dramatically higher completion rates than solo efforts. This is exactly why platforms like Ship That Code built community features.

## FAQ

### Q: What prerequisites do I need before rebuilding Redis/Git/a database?

You need solid command of a systems language (C, Rust, or Go), understanding of basic data structures (hash tables, trees), and fundamentals of network programming (sockets, TCP). Database projects additionally require understanding of disk I/O and filesystem basics. If these aren't solid yet, start with smaller command-line tool projects first.

### Q: How do I talk about rebuild projects in interviews?

This might be the biggest misconception — interviewers don't care how many lines you wrote. They care about **why you made the design decisions you did**. Why does AOF have three fsync policies? Why does a Git commit point to both a tree and a parent? Being able to articulate these tradeoffs matters far more than showing your codebase. Many engineers have landed storage-role offers on the strength of a database rebuild project alone.

### Q: How big is the gap between LLM-assisted learning and pure hand-writing?

The gap depends entirely on the depth of your questions. If you're letting the LLM generate code, the effect is diminished — you're bypassing the essential struggle. But if you treat the LLM as an "always-available mentor" — asking for conceptual explanations when stuck and analysis when debugging — results can approach pure hand-writing. The key is maintaining control of the learning pace rather than passively accepting output.

### Q: Which of the 3 projects should I do first?

Redis. No contest. Three reasons: smallest codebase (a weekend to get core functionality running), no disk I/O complexity, and the richest community resources when you get stuck. After Redis, you'll have intuition for event-driven architecture that makes Git more approachable.

## References & Community Insights

Key discussion nodes in this learning trend:

- Ship That Code course platform — https://shipthatcode.com/ — 180+ courses spanning Redis to compilers to container runtimes. Broad coverage, uneven depth.
- The "Build Your Own Redis" book completion announcement — https://build-your-own.org/redis/ — the author published the entire book free online, walking you through rebuilding Redis in C. Exceptionally high quality.
- Hacker News discussion of "How I use LLMs to learn complex topics" (835 pts / 548 comments) — https://laurentiugabriel.github.io/blog/articles/how-i-use-llms-to-learn/ — the author uses LLMs as learning partners for complex systems; the comment section debates whether LLMs undermine deep learning.
- The long-running HN community collection page — https://github.com/codecrafters-io/build-your-own-x — an aggregation of from-scratch rebuild tutorials, from databases to OS kernels to neural networks. Actively maintained by the community.
- Redis official codebase — https://github.com/redis/redis — the best reference to diff your implementation against. But wait until you've completed your core functionality — otherwise you'll drown in the details.

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "What prerequisites do I need before rebuilding Redis/Git/a database?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "You need solid command of a systems language (C, Rust, or Go), understanding of basic data structures (hash tables, trees), and fundamentals of network programming (sockets, TCP). Database projects additionally require understanding of disk I/O and filesystem basics."
    }
  }, {
    "@type": "Question",
    "name": "How do I talk about rebuild projects in interviews?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Interviewers care about why you made design decisions, not code volume. For example: Why does AOF have three fsync policies? Why does a Git commit point to both a tree and a parent? Articulating these tradeoffs matters more than showing your codebase."
    }
  }, {
    "@type": "Question",
    "name": "How big is the gap between LLM-assisted learning and pure hand-writing?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "The gap depends on the depth of your questions. If you let the LLM generate code, the effect is diminished because you bypass the struggle. But if you treat the LLM as an always-available mentor — asking for explanations when stuck — results can approach pure hand-writing."
    }
  }, {
    "@type": "Question",
    "name": "Which of the 3 projects should I do first?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Redis. Smallest codebase, no disk I/O complexity, and the richest community resources. After Redis, you'll have intuition for event-driven architecture that makes Git more approachable."
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
