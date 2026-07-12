import os
import glob

base_dir = r'site_payload/content/posts'
files = glob.glob(os.path.join(base_dir, '**', '*.md'), recursive=True)

fixed_count = 0
for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    script_start = content.find('<script type="application/ld+json">')
    if script_start != -1:
        script_end = content.find('</script>', script_start)
        is_broken = False
        
        if script_end == -1:
            is_broken = True
        else:
            json_str = content[script_start:script_end]
            if '## References' in json_str or '## 社区灵感与参考' in json_str or '{{< ad300 >}}' in json_str:
                is_broken = True
        
        if is_broken:
            print(f'Fixing {os.path.basename(f)}')
            # Remove the script block entirely from the markdown
            new_content = content[:script_start].rstrip()
            
            # Re-append references if needed (since they were possibly truncated)
            if '## References' not in new_content and '## 社区灵感与参考' not in new_content:
                if f.endswith('.en.md'):
                    new_content += '\n\n## References & Community Insights\nThe architectural perspectives and technical implementations discussed in this article were synthesized from real-world engineering experiences, post-mortems, and discussions shared across technical communities including Hacker News, Reddit, and specialized engineering blogs.\n'
                elif f.endswith('.zh.md'):
                    new_content += '\n\n## 社区灵感与参考 (References & Community Insights)\n本文探讨的架构演进与技术实现方案，深度提炼自 Hacker News、Reddit 等极客社区的真实工程师讨论、线上事故复盘（Post-mortems）以及一线技术博客的实战经验分享。\n'
            
            if '{{< ad300 >}}' not in new_content:
                new_content += '\n\n{{< ad300 >}}\n'
                
            with open(f, 'w', encoding='utf-8') as file:
                file.write(new_content)
            fixed_count += 1

print(f'Fixed {fixed_count} files.')
