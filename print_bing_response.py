import requests
import re
import urllib3

def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    url = "https://www.bing.com/images/search?q=PAPA+FEEL+577"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Content Length: {len(response.text)}")
        
        # Save first 2000 chars of HTML
        with open("bing_snippet.txt", "w", encoding="utf-8") as f:
            f.write(response.text[:50000])
            
        # Find all match urls
        matches = re.findall(r'&quot;murl&quot;:&quot;(http[^\s&]+?)&quot;', response.text)
        print(f"Found {len(matches)} matches:")
        for m in matches[:10]:
            print(f"  - {m}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
