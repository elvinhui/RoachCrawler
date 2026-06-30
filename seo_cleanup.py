import os
import glob
import re
from collections import Counter

posts_dir = "site_payload/content/posts"
# Also handle multi-lang if they are in en/ or zh/ subdirs. We just glob all .md files.
files = glob.glob(f"{posts_dir}/**/*.md", recursive=True)

# Regex to match frontmatter
yaml_pattern = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

# First pass: collect categories
cat_counts = Counter()
for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    match = yaml_pattern.search(content)
    if match:
        yaml_str = match.group(1)
        # Simple extraction of categories: ["xxx"]
        cat_match = re.search(r'categories:\s*\[(.*?)\]', yaml_str)
        if cat_match:
            cats = [c.strip(' "\'') for c in cat_match.group(1).split(',')]
            for c in cats:
                if c:
                    cat_counts[c] += 1

print("Original Categories:", cat_counts)

# Identify rare categories (count <= 2)
rare_cats = {c for c, count in cat_counts.items() if count <= 2}
print("Rare Categories to merge:", rare_cats)

# Second pass: modify files
modified_count = 0
draft_count = 0
noindex_count = 0
merged_cats_count = 0

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        original_content = file.read()
    
    match = yaml_pattern.search(original_content)
    if not match:
        continue
        
    yaml_str = match.group(1)
    body_content = original_content[match.end():]
    
    # Calculate length (naive character count excluding spaces)
    body_len = len(re.sub(r'\s', '', body_content))
    
    new_yaml_str = yaml_str
    
    needs_update = False
    
    # 1. Draft very short posts (< 50 chars)
    if body_len < 150:
        if 'draft: false' in new_yaml_str:
            new_yaml_str = new_yaml_str.replace('draft: false', 'draft: true')
            needs_update = True
            draft_count += 1
        elif 'draft:' not in new_yaml_str:
            new_yaml_str += '\ndraft: true'
            needs_update = True
            draft_count += 1
    
    # 2. Noindex short posts (< 500 chars)
    elif body_len < 800:
        if 'noindex: true' not in new_yaml_str:
            new_yaml_str += '\nnoindex: true'
            needs_update = True
            noindex_count += 1
            
    # 3. Consolidate categories
    cat_match = re.search(r'categories:\s*\[(.*?)\]', new_yaml_str)
    if cat_match:
        cats_str = cat_match.group(1)
        cats = [c.strip(' "\'') for c in cats_str.split(',')]
        new_cats = []
        changed_cat = False
        for c in cats:
            if c in rare_cats:
                new_cats.append("Tech Trends")
                changed_cat = True
            elif c:
                new_cats.append(c)
                
        if changed_cat:
            # deduplicate
            new_cats = list(set(new_cats))
            new_cats_str = ', '.join([f'"{c}"' for c in new_cats])
            new_yaml_str = re.sub(
                r'categories:\s*\[.*?\]', 
                f'categories: [{new_cats_str}]', 
                new_yaml_str
            )
            needs_update = True
            merged_cats_count += 1

    if needs_update:
        new_content = f"---\n{new_yaml_str}\n---\n{body_content}"
        with open(f, 'w', encoding='utf-8') as file:
            file.write(new_content)
        modified_count += 1

print(f"\nSummary:")
print(f"Total files checked: {len(files)}")
print(f"Files modified: {modified_count}")
print(f"Posts set to draft (< 150 chars): {draft_count}")
print(f"Posts set to noindex (< 800 chars): {noindex_count}")
print(f"Posts with categories merged: {merged_cats_count}")
