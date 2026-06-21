import urllib.request
import urllib.error
import time

def ping_search_engines(sitemap_url):
    print(f"[*] 准备向搜索引擎提交 Sitemap: {sitemap_url}")
    
    # Bing sitemap ping URL
    bing_url = f"https://www.bing.com/ping?sitemap={sitemap_url}"
    
    # Google officially deprecated their ping endpoint in late 2023, 
    # but some legacy systems still try. We will rely on robots.txt and GSC for Google.
    
    engines = {
        "Bing": bing_url
    }
    
    for name, ping_url in engines.items():
        try:
            print(f"[*] 正在 Ping {name}...")
            req = urllib.request.Request(ping_url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=10)
            if response.status == 200:
                print(f"[+] {name} Sitemap 提交成功!")
            else:
                print(f"[-] {name} Sitemap 提交返回状态码: {response.status}")
        except urllib.error.URLError as e:
            print(f"[-] {name} Sitemap 提交失败: {e}")
        except Exception as e:
            print(f"[-] {name} Sitemap 提交出现异常: {e}")
            
    print("\n[*] 提示：对于 Google，由于官方已在 2023 年底弃用 Ping 接口，")
    print("[*] 推荐首次在 Google Search Console 手动提交 Sitemap。")
    print("[*] 后续 Googlebot 会通过网站的 robots.txt 自动抓取更新。")

if __name__ == "__main__":
    sitemap = "https://www.smartinfralog.com/sitemap.xml"
    # 等待一小段时间，确保云端部署（如 Vercel/Cloudflare）已经上线了最新版本
    print("[*] 等待云端部署同步完成 (15秒)...")
    time.sleep(15)
    ping_search_engines(sitemap)
