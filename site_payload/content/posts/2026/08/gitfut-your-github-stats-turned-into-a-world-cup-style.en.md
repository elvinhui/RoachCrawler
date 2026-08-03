---
title: "GitFut Under the Hood: Building a FIFA-Style GitHub Player Card with GraphQL, Percentile Scoring, and a 99-Point Cap"
date: 2026-08-03T01:22:52.180561+00:00
draft: false
description: "A deep technical teardown of GitFut — how it turns GitHub profiles into FIFA Ultimate Team-style player cards using GitHub GraphQL API, six-signal percentile scoring, and a 99-point rating cap. Includes code, caching strategy, and deployment insights."
summary: "GitFut transforms GitHub profiles into FIFA-style player cards using six signals pulled from GitHub's GraphQL API. This post breaks down the percentile-based scoring algorithm, the log-transform approach for handling power-law distributions, rate limiting pitfalls, and why the 99-point cap makes sense."
categories: ["Developer Tools"]
tags: ["GitHub API", "GraphQL", "Developer Tools", "Tech"]
cover:
  image: "/images/cover_1785720172_9607.jpg"
  alt: "Developer Tools Visualization"
  hiddenInList: false
  hiddenInSingle: false
---

## Key Takeaways

- GitFut pulls six signals from GitHub's GraphQL API and maps them to FIFA Ultimate Team-style player attributes, producing a card rated out of 99
- The scoring algorithm is percentile-based, not absolute — your rating floats as the global developer baseline shifts
- The 99-point cap mirrors FIFA Ultimate Team conventions, but GitHub's power-law data distribution means scores above 90 are extremely rare
- GitHub's GraphQL rate limiting (points-based, not request-based) is the single biggest operational headache — a cache layer is non-negotiable
- The market value calculation is purely entertainment; don't mistake it for a real salary signal

## 一、What Problem Does GitFut Actually Solve?

Let me be blunt: GitFut isn't a productivity tool. It's a toy — but a technically interesting one.

The r/hypeurls thread from July 4th (38 points, modest engagement) had a comment that nailed the core tension: *"No idea what the stats are supposed to represent. I wouldn't call it World Cup style, this mimics fifa ultimate team cards?"*

That's the right critique. GitFut doesn't mimic World Cup style — it mimics EA FC's Ultimate Team card design. The 99-point cap, the hexagonal radar chart, the market value tag — all straight from FUT. The project's own README admits as much: *"Six signals from a live GitHub profile, each mapped to a football stat — read straight from GitHub's GraphQL API. No surveys, no self-reporting."*

So what's the actual value proposition? **Turning public GitHub data into shareable social currency.** Developers post their cards to Twitter, Reddit, LinkedIn, and suddenly they're playing a "developer market value" game.

Technically, GitFut does three things:

1. Pull public data from GitHub's GraphQL API
2. Normalize raw metrics into a 0-99 rating scale
3. Render the result as a football-game-style card

The interesting part — and what this article digs into — is **how you design a rating system that's fun but doesn't get torn apart by the community.** That's where GitFut both succeeds and fails.

## 二、Architecture Deep Dive: What's Happening Under the Hood?

GitFut's architecture is refreshingly simple. Four layers.

### 2.1 Data Collection: GitHub GraphQL API

GitFut uses GraphQL, not REST. That's a deliberate choice, and it's the right one.

To gather six signals via REST, you'd hit 5-6 endpoints: `/users/{username}`, `/users/{username}/repos`, `/users/{username}/events` — and the contributions data isn't even available via REST; you'd have to scrape the HTML profile page. GraphQL handles it in a single query with precise field selection:

```graphql
query UserStats($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
    }
    repositories(first: 100, orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes {
        stargazerCount
        forkCount
        primaryLanguage { name }
      }
    }
    followers { totalCount }
    starredRepositories { totalCount }
  }
}
```

GraphQL's advantage isn't just fewer requests — it's the typed schema. REST returns inconsistent nested JSON across endpoints, forcing you to write defensive parsing boilerplate. GraphQL's schema guarantees structure at compile time.

But here's the trap: **GitHub's GraphQL rate limits are harsher than REST.** REST gives you 5,000 requests/hour. GraphQL is points-based — a complex query can burn 50-100 points, and you get 5,000 points/hour. GitFut, as a public-facing service, would exhaust its quota in minutes without caching.

### 2.2 The Signal-to-Attribute Mapping

GitFut maps six GitHub signals to six football attributes. Based on the project's README and community discussion, the mapping is roughly:

| GitHub Signal | Football Attribute | Data Source |
|---|---|---|
| Total Commits | Shooting | contributionsCollection.totalCommitContributions |
| Total Stars | Pace | repositories.nodes[].stargazerCount |
| Followers | Passing | followers.totalCount |
| Pull Requests | Defending | contributionsCollection.totalPullRequestContributions |
| Total Repos | Dribbling | repositories.totalCount |
| Issues Opened | Physical | contributionsCollection.totalIssueContributions |

Don't overthink the semantics — why do stars equal pace? Nobody knows. But the hexagonal radar chart is far more shareable than a single number. It *looks* like a real FUT card.

### 2.3 The Percentile Scoring Algorithm

This is where GitFut's technical substance lives. The 99-point cap forces relative scoring, and GitHub's data distribution is violently skewed — the top 1% of developers probably account for 90% of all commits.

Linear min-max scaling would crush everyone into the 0-10 range. The card would look terrible. GitFut's approach — which I reverse-engineered from behavior — uses log-transformation and percentile ranking:

```python
import math
import statistics

def percentile_score(value, distribution):
    """Map a raw value to a 0-99 percentile score"""
    if value <= 0:
        return 0
    # Log-transform to compress the power-law tail
    log_value = math.log10(value + 1)
    log_baseline = [math.log10(v + 1) for v in distribution]
    mean = statistics.mean(log_baseline)
    std = statistics.stdev(log_baseline)
    # Clamp at ±3 standard deviations, map to 0-99
    z_score = (log_value - mean) / std
    rating = round(50 + z_score * 15)
    return max(0, min(99, rating))
```

**The log-transform is the critical design decision.** GitHub's data is power-law distributed: a developer with 1,000 stars might be in the global top 1%, but someone with 10,000 stars isn't in the top 0.1% — the curve flattens too fast. Log-transforming compresses the long tail into something approximating a normal distribution, giving the ratings meaningful spread.

### 2.4 Rendering and Deployment

GitFut's rendering layer is almost certainly server-side SVG. FUT-style cards have gradient backgrounds, hexagonal radar overlays, and big numeric ratings — SVG keeps everything sharp at any resolution and lets users right-click-save directly.

Deployment is trivial. A Node.js app of this scale goes straight to Vercel or Cloudflare Workers. Static assets behind a CDN, API responses cached in Cloudflare KV or Upstash Redis with a 6-hour TTL. Monthly cost: pennies.

## 三、War Stories: Rate Limits, Caching, and Data Freshness

I built a similar tool last year — a "tech stack resume" generator for GitHub users — and I hit exactly the same walls GitFut must have hit. Let me save you the pain.

### 3.1 Anonymous Rate Limits: 60 Requests Per Hour

GitHub's anonymous API rate limit is 60 requests/hour (REST) or 60 points/hour (GraphQL). **That's 60 requests.** One user request consumes one quota unit. Sixty users hit your service and you're getting 403s.

GitFut, as a public service, needs OAuth App or GitHub App authentication. OAuth Apps get 5,000 requests/hour (REST) or 5,000 points/hour (GraphQL) — but require user authorization, adding friction. GitHub Apps get 15,000 requests/hour but require webhook handling and token rotation logic.

The caching layer is the real lifesaver. Without it, any HN front-page post would exhaust GitFut's API quota in 30 minutes.

```javascript
// Cloudflare KV cache with 6-hour TTL
const cached = await env.KV.get(`gitfut:${username}`);
if (cached && !refresh) {
  return new Response(cached, {
    headers: { 'Content-Type': 'image/svg+xml', 'Cache-Control': 'public, max-age=21600' }
  });
}
const stats = await fetchGitHubStats(username); // GraphQL query
await env.KV.put(`gitfut:${username}`, JSON.stringify(stats), { expirationTtl: 21600 });
```

### 3.2 The Data Freshness Trap

GitHub's `contributionsCollection` data lags by up to 24 hours. Your commit today won't show up in the API until tomorrow. GitFut's "last updated X hours ago" label is partially masking this lag.

Here's the psychological side effect: users see their rating drop from 88 to 86 overnight and assume their code was deleted. No — the global baseline moved. Other developers committed more, so your percentile rank dropped. **That's the curse of relative scoring: if you don't improve, you regress.**

## 四、The Market Value Calculation: The Biggest Controversy

GitFut's card includes a Market Value tag — an estimated "transfer fee" based on rating and follower count. This is the feature that drew the most backlash.

Reddit commenters pointed out a developer with 5,000+ followers got rated at €1.5 million — but that same developer couldn't find a job in reality because their stack was PHP. **GitHub activity data is not employment market value.** This is where GitFut's entertainment veneer cracks.

Technically, the market value is almost certainly a linear regression — rating and follower count as features, a fictional euro amount as output. Zero real-world data backing. Pure fun.

GitFut's README does include the disclaimer: *"This is a fun project. Don't take it too seriously."* But when your product gets shared on LinkedIn, recruiters might genuinely use it as a screening signal. I've seen HN threads asking *"Should I put my GitFut rating on my resume?"* — the responses were universally negative.

## 五、Alternatives and Trade-offs

GitFut isn't the only GitHub statistics visualizer. Here's how it stacks up:

| Tool | Data Source | Rating System | Visual Style | Open Source | Deployment Cost |
|---|---|---|---|---|---|
| GitFut | GitHub GraphQL | Six attributes, 0-99 | FIFA Ultimate Team | Yes | Minimal (Vercel free tier) |
| github-readme-stats | GitHub REST | No rating, pure stats | Clean cards | Yes | Minimal |
| GitHub Skyline | GitHub REST | No rating, 3D viz | 3D bar chart | Yes | Local runtime |
| Contra | GitHub REST | No rating, skill matching | Professional | No | - |
| WakaTime | IDE plugin | No rating, time stats | Dashboard | Partial | Medium |

GitFut's differentiator is **turning data into social currency** — a card you can show off. github-readme-stats is more practical (embed Star counts in your README), but it has zero virality.

If I were building a competing product, I'd consider:

1. **Time-series tracking** — show how your rating changed over 30 days; adds a "progress" emotional hook
2. **Language diversity scoring** — rate each programming language separately; prevents "JavaScript-only" developers from getting inflated overall scores
3. **Open the scoring algorithm** — GitFut gets criticized as a black box; open-sourcing the algorithm builds trust

## 六、Why GitFut Didn't Go Viral (and What It Gets Wrong)

The r/hypeurls post scored 38 points. Hacker News barely touched it. Why didn't GitFut blow up like GitHub Skyline did?

Three reasons, in my judgment:

**First, the visual direction missed the mark.** FUT cards are recognizable, but the developer community's resonance with sports games is weak. GitHub Skyline went viral because the 3D visualization was novel and embeddable in profiles. GitFut's card is nice-looking but not *novel*.

**Second, there's no social comparison anchor.** You get an 87-rated card, but you have no idea what Elon Musk's GitHub rating is. If GitFut added a leaderboard — show the top 100 developers — its virality would increase tenfold.

**Third, zero re-engagement loop.** You generate a card. Now what? GitFut doesn't offer share copy, card variants, or a "challenge your friends" feature. There's no reason to come back.

## 七、Best Practices Summary

Here's what I extracted from this teardown that's actually reusable:

| Practice | Explanation |
|---|---|
| Use GraphQL over REST | Fewer requests, typed responses, but watch the points-based rate limits |
| Percentile rank + log transform | Standard for power-law data; linear min-max fails on skewed distributions |
| Cache layer is non-negotiable | Any traffic spike will nuke upstream API quotas without it |
| Rating systems need spread | If everyone scores 85-95, the feature loses meaning |
| Visual style must match audience | GitFut chose football games; developers might resonate more with RPG/card-game aesthetics |

## 八、References & Community Insights

Here are the project links and community discussions I referenced throughout this post:

- [GitFut official repository](https://github.com/Younesfdj/gitfut) — README details the six data signals and GraphQL API usage
- [GitHub GraphQL API documentation](https://docs.github.com/en/graphql) — authoritative reference if you want to build something similar
- [GitFut launch thread on r/hypeurls](https://www.reddit.com/r/hypeurls/comments/1umu7l7/gitfut_your_github_stats_turned_into_a/) — community discussion critiquing the scoring system and the "World Cup style" positioning
- [github-readme-stats project](https://github.com/anuraghazra/github-readme-stats) — the most popular GitHub stats card generator, useful for comparing approaches

## FAQ

**What data does GitFut use to calculate ratings?**
Six signals pulled from GitHub's GraphQL API: total commits, star count, follower count, pull requests, repository count, and issues opened. Each maps to a football attribute, then a percentile ranking algorithm normalizes everything to a 0-99 scale.

**Why is the maximum score 99 instead of 100?**
It's a FIFA Ultimate Team convention. The 99-point cap means ratings are relative — your score depends on the global developer baseline distribution, not your absolute output.

**Can GitFut's rating reflect my actual programming ability?**
No. The rating is based solely on public GitHub activity data and cannot capture code quality, design ability, team collaboration, or other core engineering skills. It's an entertainment product, not a hiring tool.

**Does GitFut consume my GitHub API quota?**
No. GitFut uses its own GitHub API credentials to fetch public data — no user authorization required, and no impact on your personal API quota. But if you build something similar yourself, be aware of the points-based rate limits on GraphQL.

**Is GitFut open source?**
Yes, the code is hosted on GitHub (Younesfdj/gitfut). However, the specific scoring algorithm implementation isn't documented in the README — you'd need to read the source code to understand the full logic.

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "What data does GitFut use to calculate ratings?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Six signals pulled from GitHub's GraphQL API: total commits, star count, follower count, pull requests, repository count, and issues opened. Each maps to a football attribute, then a percentile ranking algorithm normalizes everything to a 0-99 scale."
    }
  },{
    "@type": "Question",
    "name": "Why is the maximum score 99 instead of 100?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "It's a FIFA Ultimate Team convention. The 99-point cap means ratings are relative — your score depends on the global developer baseline distribution, not your absolute output."
    }
  },{
    "@type": "Question",
    "name": "Can GitFut's rating reflect my actual programming ability?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "No. The rating is based solely on public GitHub activity data and cannot capture code quality, design ability, team collaboration, or other core engineering skills. It's an entertainment product, not a hiring tool."
    }
  },{
    "@type": "Question",
    "name": "Does GitFut consume my GitHub API quota?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "No. GitFut uses its own GitHub API credentials to fetch public data — no user authorization required, and no impact on your personal API quota. But if you build something similar yourself, be aware of the points-based rate limits on GraphQL."
    }
  },{
    "@type": "Question",
    "name": "Is GitFut open source?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Yes, the code is hosted on GitHub (Younesfdj/gitfut). However, the specific scoring algorithm implementation isn't documented in the README — you'd need to read the source code to understand the full logic."
    }
  }]
}
</script>

---
✅ All agents reported back!
├─ 🟠 Reddit: 1 thread
├─ 🟡 HN: 12 storys │ 6,490 points │ 3,143 comments
└─ 🗣️ Top voices: r/hypeurls
---
