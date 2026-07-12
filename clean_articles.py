import os
import glob
import re

base = r'C:\Users\KATANA 17 B13V\.gemini\antigravity\worktrees\RoachCrawler\diversify-article-topics\site_payload\content\posts'
md_files = glob.glob(os.path.join(base, '*.md'))

# Phase 1: Remove {{< ad300 >}}
for f in md_files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    if '{{< ad300 >}}' in content:
        content = content.replace('{{< ad300 >}}', '')
        with open(f, 'w', encoding='utf-8') as file:
            file.write(content)
        print(f"Removed ad300 from {os.path.basename(f)}")

# Phase 2: Find shortest articles and noindex them
# We'll measure by length of content (words) for .en.md files and apply to both en and zh
en_files = glob.glob(os.path.join(base, '*.en.md'))
word_counts = []

for f in en_files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    # rough word count
    words = len(content.split())
    word_counts.append((words, f))

# Sort by length
word_counts.sort()

# Take the bottom 40
bottom_40 = word_counts[:40]

def add_noindex(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    # Check if noindex is already there
    has_noindex = any('noindex:' in line for line in lines)
    if has_noindex:
        return
        
    # Find the end of frontmatter
    if len(lines) > 0 and lines[0].strip() == '---':
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                # Insert draft and noindex before the closing ---
                lines.insert(i, 'draft: true\n')
                break
                
    with open(filepath, 'w', encoding='utf-8') as file:
        file.writelines(lines)

for count, f in bottom_40:
    base_name = f.replace('.en.md', '')
    zh_file = base_name + '.zh.md'
    
    add_noindex(f)
    if os.path.exists(zh_file):
        add_noindex(zh_file)
    print(f"Drafted (length {count}): {os.path.basename(f)}")

print("Done processing articles.")
