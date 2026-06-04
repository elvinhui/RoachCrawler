# scripts/import_json_to_db.py
import json
import sqlite3
import os

def import_json_matrix():
    # 路径配置
    base_dir = os.path.dirname(__file__)
    json_path = os.path.join(base_dir, '..', 'keywords.json')
    db_path = os.path.join(base_dir, '..', 'roach_matrix.db')

    # 检查文件是否存在
    if not os.path.exists(json_path):
        print(f"[-] 找不到种子文件: {json_path}")
        return
    if not os.path.exists(db_path):
        print("[-] 找不到数据库，请先运行 core_db.py 初始化建表。")
        return

    print("[*] 正在解析 JSON 种子文件...")
    with open(json_path, 'r', encoding='utf-8') as f:
        seed_data = json.load(f)

    print("[*] 正在连接 SQLite 矩阵中枢...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    success_count = 0
    skip_count = 0

    for item in seed_data:
        keyword = item.get("keyword")
        intent = item.get("intent")
        niche = item.get("niche")
        status = item.get("status", "pending") # 如果 JSON 里是 processing，可以强制重置为 pending
        expected_structure = item.get("expected_structure")

        try:
            # 使用 INSERT 语句，利用 UNIQUE 约束防止重复导入
            cursor.execute('''
            INSERT INTO seo_matrix (keyword, intent, niche, status, expected_structure)
            VALUES (?, ?, ?, ?, ?)
            ''', (keyword, intent, niche, status, expected_structure))
            success_count += 1
        except sqlite3.IntegrityError:
            # 如果数据库里已经有这个词了，就跳过
            skip_count += 1

    conn.commit()
    conn.close()

    print(f"[+] 导入完成！")
    print(f"    -> 成功灌入新节点: {success_count} 个")
    print(f"    -> 重复跳过节点: {skip_count} 个")

if __name__ == "__main__":
    import_json_matrix()