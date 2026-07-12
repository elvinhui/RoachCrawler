import os, glob, re

base = r'C:\Users\KATANA 17 B13V\.gemini\antigravity\worktrees\RoachCrawler\diversify-article-topics\site_payload\content\posts'
en_files = sorted(glob.glob(os.path.join(base, '*.en.md')))

dates = {}
for f in en_files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read(500)
    
    m = re.search(r'date:\s*"?(\d{4}-\d{2}-\d{2})', content)
    if m:
        date = m.group(1)
        month = date[:7]
        dates[month] = dates.get(month, 0) + 1

for month in sorted(dates.keys()):
    print(f'{month}: {dates[month]} articles')
