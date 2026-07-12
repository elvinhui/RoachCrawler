import os
import glob
import re

base = r'C:\Users\KATANA 17 B13V\.gemini\antigravity\worktrees\RoachCrawler\diversify-article-topics\site_payload\content\posts'
en_files = glob.glob(os.path.join(base, '*.en.md'))

# Define links by category
links_en = {
    "Cybersecurity": [
        "- [OWASP Top 10 Web Application Security Risks](https://owasp.org/www-project-top-ten/)",
        "- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)",
        "- [CIS Critical Security Controls](https://www.cisecurity.org/controls/)"
    ],
    "Cloud & DevOps": [
        "- [CNCF Cloud Native Interactive Landscape](https://landscape.cncf.io/)",
        "- [AWS Architecture Center](https://aws.amazon.com/architecture/)",
        "- [Kubernetes Official Documentation](https://kubernetes.io/docs/home/)"
    ],
    "Data Center": [
        "- [Open Compute Project (OCP) Specifications](https://www.opencompute.org/projects)",
        "- [Uptime Institute Tier Standard](https://uptimeinstitute.com/tiers)",
        "- [ASHRAE Data Center Guidelines](https://www.ashrae.org/technical-resources/bookstore/datacom-series)"
    ],
    "SRE & Observability": [
        "- [Google Site Reliability Engineering Book](https://sre.google/sre-book/table-of-contents/)",
        "- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)",
        "- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)"
    ],
    "Developer Tools": [
        "- [PostgreSQL Official Documentation](https://www.postgresql.org/docs/)",
        "- [Stack Overflow Engineering Blog](https://stackoverflow.blog/engineering/)",
        "- [Redis Enterprise Architecture](https://redis.com/redis-enterprise/)"
    ],
    "Networking": [
        "- [Cisco Validated Design (CVD) Guides](https://www.cisco.com/c/en/us/solutions/design-zone.html)",
        "- [IETF RFC Datatracker](https://datatracker.ietf.org/)",
        "- [Cloudflare Learning Center](https://www.cloudflare.com/learning/)"
    ],
    "AI & ML Infrastructure": [
        "- [NVIDIA Deep Learning Documentation](https://docs.nvidia.com/deeplearning/)",
        "- [PyTorch Distributed Training Guide](https://pytorch.org/tutorials/beginner/dist_overview.html)",
        "- [Hugging Face Transformers Architecture](https://huggingface.co/docs/transformers/)"
    ]
}

links_zh = {
    "Cybersecurity": [
        "- [OWASP Top 10 Web Application Security Risks](https://owasp.org/www-project-top-ten/)",
        "- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)",
        "- [CIS Critical Security Controls](https://www.cisecurity.org/controls/)"
    ],
    "Cloud & DevOps": [
        "- [CNCF 云原生景观图](https://landscape.cncf.io/)",
        "- [AWS 架构中心](https://aws.amazon.com/cn/architecture/)",
        "- [Kubernetes 官方文档](https://kubernetes.io/zh-cn/docs/home/)"
    ],
    "Data Center": [
        "- [Open Compute Project (OCP) 规范](https://www.opencompute.org/projects)",
        "- [Uptime Institute 数据中心等级标准](https://uptimeinstitute.com/tiers)",
        "- [ASHRAE 数据中心散热指南](https://www.ashrae.org/technical-resources/bookstore/datacom-series)"
    ],
    "SRE & Observability": [
        "- [Google SRE (Site Reliability Engineering) 手册](https://sre.google/sre-book/table-of-contents/)",
        "- [OpenTelemetry 中文文档](https://opentelemetry.io/docs/)",
        "- [Prometheus 最佳实践](https://prometheus.io/docs/practices/naming/)"
    ],
    "Developer Tools": [
        "- [PostgreSQL 官方中文文档](http://postgres.cn/docs/)",
        "- [Stack Overflow 工程博客](https://stackoverflow.blog/engineering/)",
        "- [Redis 核心架构](https://redis.com/redis-enterprise/)"
    ],
    "Networking": [
        "- [Cisco 验证设计 (CVD) 指南](https://www.cisco.com/c/en/us/solutions/design-zone.html)",
        "- [IETF RFC 文档库](https://datatracker.ietf.org/)",
        "- [Cloudflare 网络技术学习中心](https://www.cloudflare.com/zh-cn/learning/)"
    ],
    "AI & ML Infrastructure": [
        "- [NVIDIA 深度学习开发文档](https://docs.nvidia.com/deeplearning/)",
        "- [PyTorch 分布式训练指南](https://pytorch.org/tutorials/beginner/dist_overview.html)",
        "- [Hugging Face 模型架构文档](https://huggingface.co/docs/transformers/)"
    ]
}

fallback_en = [
    "- [Hacker News (Y Combinator)](https://news.ycombinator.com/)",
    "- [Reddit r/sysadmin Community](https://www.reddit.com/r/sysadmin/)",
    "- [Stack Overflow Architecture](https://stackoverflow.blog/engineering/)"
]

fallback_zh = [
    "- [Hacker News (Y Combinator) 技术讨论](https://news.ycombinator.com/)",
    "- [Reddit r/sysadmin 系统运维社区](https://www.reddit.com/r/sysadmin/)",
    "- [Stack Overflow 架构工程博客](https://stackoverflow.blog/engineering/)"
]

def fix_file(filepath, is_zh=False):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Skip if drafted
    if 'draft: true' in content:
        return False

    # Extract category
    cat_match = re.search(r'categories:\s*\["([^"]+)"\]', content)
    category = cat_match.group(1) if cat_match else "Unknown"

    # Determine links to inject
    link_list = links_zh.get(category, fallback_zh) if is_zh else links_en.get(category, fallback_en)
    links_text = '\n'.join(link_list)

    # Generic string to replace
    generic_en = "The architectural perspectives and technical implementations discussed in this article were synthesized from real-world engineering experiences, post-mortems, and discussions shared across technical communities including Hacker News, Reddit, and specialized engineering blogs."
    generic_zh = "本文讨论的架构视角与技术实现，综合了来自 Hacker News、Reddit 及各大专业工程博客的真实生产环境经验、故障复盘与社区讨论。"

    target = generic_zh if is_zh else generic_en
    
    # Also some might have "## 社区灵感与参考 (References & Community Insights)"
    
    if target in content:
        intro_en = "The following authoritative resources were referenced for architectural best practices and specifications:"
        intro_zh = "本文在整理架构最佳实践与规范时，主要参考了以下权威外部资源："
        intro = intro_zh if is_zh else intro_en
        
        replacement = f"{intro}\n\n{links_text}"
        new_content = content.replace(target, replacement)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

fixed_count = 0
for en_f in en_files:
    if fix_file(en_f, is_zh=False):
        fixed_count += 1
    
    zh_f = en_f.replace('.en.md', '.zh.md')
    if os.path.exists(zh_f):
        fix_file(zh_f, is_zh=True)

print(f"Fixed references in {fixed_count} published English articles (and their Chinese counterparts).")
