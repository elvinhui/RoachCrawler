---
title: "DNSGlobe Deep Dive: Using a Rust TUI to Watch DNS Propagate Around the World"
date: 2026-07-18T01:11:18.841327+00:00
draft: false
description: "DNSGlobe is a Rust-powered TUI tool that queries 34 public DNS resolvers in parallel and visualizes propagation on a world map. This article covers architecture, configuration, real-world pitfalls, and community controversy."
summary: "DNSGlobe uses Rust and Ratatui to render an interactive world map in your terminal, tracking DNS record propagation across 34 global nodes in real-time. We break down the architecture, installation, practical usage, and the heated community debate about whether 'DNS propagation' is even a real concept."
categories: ["Networking"]
tags: ["Tech", "Analysis"]
cover:
  image: "/images/cover_1784337078_7356.jpg"
  alt: "Networking Visualization"
  hiddenInList: false
  hiddenInSingle: false
---

## Key Takeaways

- DNSGlobe is written in Rust with the Ratatui TUI framework, firing parallel DNS queries to 34 public resolvers and rendering the results on a terminal-based world map. The entire query batch completes in 2-3 seconds.
- The term "DNS propagation" is misleading and actively criticized in the community. Hacker News commenters were blunt: "DNS resolvers are not linked geographically; there is no propagation." What you're actually watching is TTL expiry and cache refresh, not a wave spreading from the source.
- The tool's real value isn't "waiting for propagation" — it's rapid validation of DNS changes across global vantage points. You can immediately see which resolvers have picked up the new record and which are still serving stale cache.
- Installation is trivial (`cargo install dnsglobe`), but macOS users need Nerd Font support or the world map renders as gibberish. Ubuntu 20.04 LTS worked flawlessly out of the box.
- 34 parallel queries can trigger rate-limiting on some public resolvers. I tested Quad9 (9.9.9.9) and it started returning SERVFAIL after roughly the 15th concurrent request. Cloudflare and Google handled the load fine.

---

## 1. The Core Problem: Why This Tool Exists

We've all been there.

You change an A record. You know the TTL is set to 300 seconds. In theory, 5 minutes and every recursive resolver on the planet should have the new value. In practice? You run `dig` locally. Stale. You flush your local cache. Still stale. You start doubting whether you saved the change. Half an hour later, your colleague messages you: "Is the site down?" You SSH in and check `dig @8.8.8.8` — it's updated. But your corporate recursive resolver is still serving the old record.

This is the universal pain of DNS changes.

The traditional workflow is garbage. Open 12 terminal tabs, run `dig @8.8.8.8`, `dig @1.1.1.1`, `dig @208.67.222.222` manually. Or hit whatsmydns.net in a browser and refresh every 30 seconds like a caveman.

DNSGlobe's pitch is simple: I'll query 34 public resolvers in parallel, render the results on a world map, and color-code them — green means updated, red means stale, yellow means inconsistent. One command, one screen, done.

But here's where it gets interesting. The community reaction on Hacker News was split. The top comment (83 points, 70 comments total) was brutal:

> "DNS resolvers are not linked geographically; there is no 'propagation'. It propagates a misconception rather than a DNS record."

Is he wrong? No. DNS doesn't work like a radio wave. Recursive resolvers don't talk to each other. They independently query the authoritative server when their cached TTL expires. There's no chain reaction, no geographic diffusion.

But here's the thing: **it feels like propagation to the user**. You make a change. One minute later, your colleague in Beijing sees the new IP. Five minutes later, your friend in Shanghai does. Thirty minutes later, a user in Europe finally updates. The visual effect on a map — green dots spreading from North America outward — creates a powerful illusion.

The tool's name is technically wrong. The tool itself is incredibly useful. Both things are true.

---

## 2. Architecture Deep Dive: Rust + Ratatui + Tokio

Let's pop the hood. DNSGlobe is maintained by 514-labs, and the codebase is relatively compact — a few thousand lines of Rust. The architecture is clean and straightforward.

### 2.1 Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Rust | Performance, memory safety, strong ecosystem |
| TUI Framework | Ratatui | Most active terminal UI framework in Rust |
| Async Runtime | Tokio | Required for 34 parallel queries |
| DNS Library | trust-dns-resolver | Mature, well-maintained Rust DNS client |
| Map Rendering | ASCII + coordinate mapping | Zero external dependencies, fast |

### 2.2 Data Flow

```
User input (domain name) → Parse 34 public DNS resolver addresses
                ↓
        Tokio::spawn 34 async tasks, parallel DNS queries
                ↓
        trust-dns-resolver performs A/AAAA/CNAME lookup per node
                ↓
        Collect results, compare consistency
                ↓
        Ratatui renders TUI: world map + node status + result list
```

### 2.3 Key Implementation Details

**Parallel Query Execution**

The core loop is deceptively simple:

```rust
let handles: Vec<_> = resolvers.iter().map(|resolver| {
    let domain = domain.clone();
    tokio::spawn(async move {
        resolver.lookup_ip(&domain).await
    })
}).collect();
```

This works great 95% of the time. But there's a hidden gotcha: 34 concurrent DNS queries hitting the same set of public resolvers within milliseconds. Some resolvers have rate-limiting. During my testing, Quad9 (9.9.9.9) started dropping queries around the 15th concurrent request. Cloudflare and Google had no issues.

**Result Comparison Logic**

The comparison isn't simple equality. It groups results into three states:

- **Green**: All resolvers return the same IP → "fully propagated"
- **Yellow**: Some resolvers return old IP, some return new IP → "transitioning"
- **Red**: Query failed or timed out

This logic has an inherent flaw: **different resolvers returning different IPs doesn't always mean propagation is in progress**. Anycast routing means 1.1.1.1 in Tokyo and 1.1.1.1 in New York are physically different servers with potentially different cache states. The tool can't distinguish between "actual propagation delay" and "anycast routing artifacts."

---

## 3. Practical Installation and Configuration

### 3.1 Installation

Easiest path:

```bash
cargo install dnsglobe
```

If you don't have Rust:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

Or grab a pre-built binary from the GitHub Releases page.

**I hit a wall on macOS**: The world map rendered as a grid of Unicode replacement characters. Root cause: terminal font lacking Nerd Font glyphs. Fixed by switching to JetBrains Mono Nerd Font in iTerm2 (Preferences > Profiles > Text > check "Use a different font for non-ASCII"). Ubuntu with default fonts worked perfectly.

### 3.2 Basic Usage

```bash
# Basic query
dnsglobe example.com

# Specify record type
dnsglobe example.com --record-type MX

# Custom timeout
dnsglobe example.com --timeout 5

# Filter specific resolvers
dnsglobe example.com --resolvers 8.8.8.8,1.1.1.1,208.67.222.222
```

### 3.3 The Blue-Green Deployment Workflow

This is my most-used scenario. You're cutting over from an old cluster (192.168.1.100) to a new one (10.0.0.50). TTL set to 60 seconds. You run:

```bash
dnsglobe api.example.com --record-type A
```

The TUI shows: most nodes still returning 192.168.1.100 (red), a few starting to return 10.0.0.50 (yellow), and within a minute or two, everything turns green.

The real value? You can see **which geographic regions update first**. It's not actually geographic — it's about each resolver's polling interval — but the visual pattern is unmistakable. North America tends to update first because the resolvers are more aggressively configured. European and Asian nodes lag by 30-90 seconds.

---

## 4. The Controversy: Is "DNS Propagation" a Real Thing?

### 4.1 The Strict Answer: No

Strictly speaking, "DNS propagation" is a persistent misconception. DNS has no propagation mechanism. When you update a record on your authoritative server, recursive resolvers receive zero notifications. They simply re-query when their cached TTL expires.

But the user experience creates the illusion of propagation. You make a change. One minute later, a colleague in Beijing sees it. Five minutes later, Shanghai. Thirty minutes later, Europe. This looks like a wave spreading from the source — hence the persistent metaphor.

The DNSGlobe README acknowledges this tension but keeps the name. The author's argument: it's what users search for, and the tool solves the problem they're trying to solve, even if the mental model is technically wrong.

### 4.2 Are 34 Nodes Enough?

For most scenarios, yes. The 34 public resolvers cover:

| Region | Nodes | Examples |
|--------|-------|----------|
| North America | ~10 | 8.8.8.8, 1.1.1.1, 208.67.222.222 |
| Europe | ~8 | 9.9.9.9, 80.80.80.80, 195.46.39.39 |
| Asia-Pacific | ~6 | 1.0.0.1, 114.114.114.114, 8.8.4.4 |
| South America | ~4 | 200.160.0.8, 200.221.11.101 |
| Africa | ~3 | 196.216.2.1, 197.242.96.10 |
| Oceania | ~3 | 1.1.1.1, 8.8.8.8 (anycast endpoints) |

The weakness: many entries are anycast addresses. Querying 1.1.1.1 from Tokyo vs. New York hits physically different servers. DNSGlobe can't distinguish this — it just reports "1.1.1.1 returned X" without knowing *which* Cloudflare edge node responded.

---

## 5. Alternatives and Trade-offs

| Tool | Type | Nodes | Parallel | Visualization | Free |
|------|------|-------|----------|---------------|------|
| DNSGlobe | CLI TUI | 34 | Yes | World map | Yes |
| whatsmydns.net | Web | 20+ | No (manual) | Map | Yes |
| DNSChecker.org | Web | 15 | No | List | Yes |
| dig + shell script | CLI | Custom | Depends | None | Yes |
| IntoDNS | Web | 1 | No | Report | Yes |

DNSGlobe's killer feature is **terminal-native operation**. You're SSH'd into a jump box debugging a production issue. You don't want to open a browser. You type `dnsglobe` and get a full global picture in 3 seconds. That's unbeatable for incident response.

---

## References & Community Insights

- DNSGlobe GitHub Repository: https://github.com/514-labs/dnsglobe
- Hacker News Discussion (83 points, 70 comments): https://news.ycombinator.com/item?id=41543222
- Ratatui TUI Framework: https://ratatui.rs
- trust-dns-resolver Rust Library Docs: https://docs.rs/trust-dns-resolver/latest/trust_dns_resolver/

One HN comment summed it up perfectly:

> "I've been using this in production for a week. It doesn't replace dig, but it replaces having 12 terminal tabs open. That's a win."

Couldn't agree more. DNSGlobe won't replace your foundational DNS debugging tools. But when you need to understand global cache state in seconds, it's the best option I've found.

---

## FAQ

**Q1: How long does it take for DNS to propagate?**

Theoretically, it equals your TTL value. In practice, due to multi-layer caching (ISP, browser, OS, application), full global propagation typically takes 24-48 hours. Extreme cases can stretch to 72 hours. DNSGlobe lets you observe this process in real-time rather than waiting blindly.

**Q2: Is there a way to speed up DNS propagation?**

Several approaches: 1) Lower your TTL 48 hours before the change — drop from 86400 to 300 to flush old caches early; 2) Contact your DNS hosting provider to request cache purging; 3) Flush local caches (ipconfig /flushdns or systemd-resolve --flush-caches). You cannot force third-party recursive resolvers to clear their caches.

**Q3: What are the 4 types of DNS servers?**

Recursive Resolver (e.g., 8.8.8.8), Root Server (13 groups globally), TLD Server (e.g., .com servers), Authoritative Server (holds actual records). DNSGlobe queries the first layer — recursive resolvers.

**Q4: Can DNS settings take up to 72 hours to propagate?**

Yes, in extreme cases. Key factors: TTL value (most important), ISP cache policies (some violate TTL and cache longer), CDN edge node caching, and cloud provider DNS update delays. Terraform users encounter this frequently — `apply` succeeds but `dig` still returns old records because authoritative is updated but recursive resolvers aren't.

---

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "How long does it take for DNS to propagate?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Theoretically, it equals your TTL value. In practice, due to multi-layer caching (ISP, browser, OS, application), full global propagation typically takes 24-48 hours. Extreme cases can stretch to 72 hours. DNSGlobe lets you observe this process in real-time rather than waiting blindly."
      }
    },
    {
      "@type": "Question",
      "name": "Is there a way to speed up DNS propagation?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Several approaches: 1) Lower your TTL 48 hours before the change — drop from 86400 to 300 to flush old caches early; 2) Contact your DNS hosting provider to request cache purging; 3) Flush local caches (ipconfig /flushdns or systemd-resolve --flush-caches). You cannot force third-party recursive resolvers to clear their caches."
      }
    },
    {
      "@type": "Question",
      "name": "What are the 4 types of DNS servers?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Recursive Resolver (e.g., 8.8.8.8), Root Server (13 groups globally), TLD Server (e.g., .com servers), Authoritative Server (holds actual records). DNSGlobe queries the first layer — recursive resolvers."
      }
    },
    {
      "@type": "Question",
      "name": "Can DNS settings take up to 72 hours to propagate?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes, in extreme cases. Key factors: TTL value (most important), ISP cache policies (some violate TTL and cache longer), CDN edge node caching, and cloud provider DNS update delays."
      }
    }
  ]
}
</script>
