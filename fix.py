import os, glob, re
count = 0
for f in glob.glob('site_payload/content/posts/*.md'):
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # We want to find {{< ad300 >}} and remove it entirely from all posts to be safe
    # Or just remove it if it's inside a codeblock.
    # Actually, removing it entirely from all posts is 100% safe to fix the bug, 
    # but the user might want ads. Let's just remove it if it's between ``` and ```.
    
    def replacer(m):
        block = m.group(0)
        if 'ad300' in block:
            return block.replace('{{< ad300 >}}', '')
        return block

    new_content = re.sub(r'```.*?```', replacer, content, flags=re.DOTALL)
    new_content = re.sub(r'`[^`]*`', replacer, new_content, flags=re.DOTALL)
    
    if new_content != content:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(new_content)
        count += 1
        print(f"Fixed code block in {f}")

print(f"Total files fixed: {count}")
