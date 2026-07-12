import os
import glob
import re
import urllib.parse
import httpx
from datetime import datetime

base_dir = r'C:\Users\KATANA 17 B13V\.gemini\antigravity\worktrees\RoachCrawler\diversify-article-topics\site_payload'
posts_dir = os.path.join(base_dir, 'content', 'posts')
images_dir = os.path.join(base_dir, 'static', 'images')
os.makedirs(images_dir, exist_ok=True)

md_files = glob.glob(os.path.join(posts_dir, '*.md'))

client = httpx.Client(timeout=30.0)

for filepath in md_files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the image URL
    match = re.search(r'image:\s*"(https://image\.pollinations\.ai/prompt/[^"]+)"', content)
    if not match:
        continue
        
    old_url = match.group(1)
    
    # Generate a safe filename
    base_name = os.path.basename(filepath).replace('.zh.md', '').replace('.en.md', '')
    image_filename = f"{base_name}_cover.jpg"
    image_path = os.path.join(images_dir, image_filename)
    
    # Only download if it doesn't already exist
    if not os.path.exists(image_path):
        print(f"Downloading {old_url} for {base_name}...")
        try:
            resp = client.get(old_url)
            resp.raise_for_status()
            with open(image_path, 'wb') as img_f:
                img_f.write(resp.content)
        except Exception as e:
            print(f"Failed to download image for {filepath}: {e}")
            continue

    # Update the markdown file
    new_url = f"/images/{image_filename}"
    new_content = content.replace(f'image: "{old_url}"', f'image: "{new_url}"')
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath} to use local image {new_url}")

client.close()
print("Finished migrating cover images to local static assets.")
