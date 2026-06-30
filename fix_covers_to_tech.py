import os
import glob
import re
import random

CATEGORY_COVERS = {
    "Cloud & DevOps": [
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=1200&auto=format&fit=crop", # Cloud earth
        "https://images.unsplash.com/photo-1614064641913-6b20a71f1fd5?q=80&w=1200&auto=format&fit=crop", # Code abstract
    ],
    "Cybersecurity": [
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?q=80&w=1200&auto=format&fit=crop", # Matrix locks
        "https://images.unsplash.com/photo-1563206767-5b18f218e8de?q=80&w=1200&auto=format&fit=crop", # Padlock
    ],
    "Data Center": [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=1200&auto=format&fit=crop", # Server cooling
        "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?q=80&w=1200&auto=format&fit=crop", # Server racks
    ],
    "SRE & Observability": [
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=1200&auto=format&fit=crop", # Dashboards
    ],
    "AI & ML Infrastructure": [
        "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?q=80&w=1200&auto=format&fit=crop", # AI abstract
        "https://images.unsplash.com/photo-1677442136019-21780ecad995?q=80&w=1200&auto=format&fit=crop", # AI generative
    ],
    "Networking": [
        "https://images.unsplash.com/photo-1544197150-b99a580bb7a8?q=80&w=1200&auto=format&fit=crop", # Network cables
        "https://images.unsplash.com/photo-1551721434-8b94ddff0e6d?q=80&w=1200&auto=format&fit=crop", # Switches
    ],
    "Developer Tools": [
        "https://images.unsplash.com/photo-1555066931-4365d14bab8c?q=80&w=1200&auto=format&fit=crop", # Code screen
    ],
    "Infrastructure": [
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=1200&auto=format&fit=crop", # Cloud
    ],
    "Tech Trends": [
        "https://images.unsplash.com/photo-1519389950473-47ba0277781c?q=80&w=1200&auto=format&fit=crop", # Workspace
    ],
    "Default": [
        "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?q=80&w=1200&auto=format&fit=crop", # Abstract tech
    ]
}

posts_dir = "site_payload/content/posts"
files = glob.glob(f"{posts_dir}/**/*.md", recursive=True)

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Only process if it has a picsum or loremflickr image
    if 'picsum.photos' not in content and 'loremflickr.com' not in content:
        continue
    
    # Find the category
    category_match = re.search(r'categories:\s*\["(.*?)"\]', content)
    
    selected_category = "Default"
    if category_match:
        cat = category_match.group(1)
        # Find closest match in our dictionary
        for key in CATEGORY_COVERS.keys():
            if cat.lower() == key.lower() or cat.lower() in key.lower():
                selected_category = key
                break
    
    # Pick a random image from the selected category
    new_image_url = random.choice(CATEGORY_COVERS[selected_category])
    
    # Replace the old image URL
    new_content = re.sub(
        r'image:\s*"(https://(picsum\.photos|loremflickr\.com).*?)"', 
        f'image: "{new_image_url}"', 
        content
    )
    
    with open(f, 'w', encoding='utf-8') as file:
        file.write(new_content)
    
print(f"Processed {len(files)} files.")
