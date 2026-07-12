import os
import glob
import re
from collections import Counter

files = glob.glob('site_payload/content/posts/**/*.md', recursive=True)
cats = Counter()
tags = Counter()
short_files = []

for f in files:
    try:
        with open(f, encoding='utf-8') as file:
            c = file.read()
            word_count = len(re.findall(r'\b\w+\b', c)) + len(re.findall(r'[\u4e00-\u9fff]', c)) # words + chinese chars
            if word_count < 300:
                short_files.append(f)
                
            m_cat = re.search(r'categories:\s*\[(.*?)\]', c)
            if m_cat:
                cat_list = m_cat.group(1).replace('"', '').replace("'", "").split(',')
                cats.update([cat.strip() for cat in cat_list if cat.strip()])
                
            m_tag = re.search(r'tags:\s*\[(.*?)\]', c)
            if m_tag:
                tgs = m_tag.group(1).replace('"', '').replace("'", "").split(',')
                tags.update([t.strip() for t in tgs if t.strip()])
    except Exception as e:
        print(f"Error reading {f}: {e}")

print(f"Total articles: {len(files)}")
print(f"Short articles (<300 words/chars): {len(short_files)}")
print("Categories:")
for k, v in cats.items():
    print(f"  {k}: {v}")
print(f"Total tags: {len(tags)}")
print(f"Tags with only 1 post: {sum(1 for v in tags.values() if v == 1)}")
