import requests
import re
import urllib3

def get_bing_image_url(query):
    url = f"https://www.bing.com/images/search?q={requests.utils.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
    }
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        if response.status_code == 200:
            matches = re.findall(r'&quot;murl&quot;:&quot;(http[^\s&]+?)&quot;', response.text)
            if not matches:
                matches = re.findall(r'"murl":"(http[^\s"]+?)"', response.text)
            
            for match in matches:
                if any(x in match.lower() for x in [".jpg", ".png", ".jpeg", ".webp", "susercontent", "shopee", "lazada", "alicdn"]):
                    return match
            if matches:
                return matches[0]
    except Exception as e:
        print(f"Error searching Bing for '{query}': {e}")
    return None

def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Test query with cosmetic context
    query = "PAPA FEEL 577 เซรั่ม skincare cosmetic"
    print(f"Searching for: {query}")
    img_url = get_bing_image_url(query)
    print(f"Result image URL: {img_url}")

if __name__ == "__main__":
    main()
