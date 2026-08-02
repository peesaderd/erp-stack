import requests
import re
import urllib3

def get_google_image_url(query):
    # Google Images search url
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}&tbm=isch"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        if response.status_code == 200:
            # Look for image URLs in the HTML response.
            # Google Images basic HTML search returns URLs in format like: src="https://encrypted-tbn0.gstatic.com/images?q=tbn:..."
            matches = re.findall(r'src="(https://encrypted-tbn[^"]+?)"', response.text)
            if not matches:
                # Also try matching standard image links
                matches = re.findall(r'imgurl=(http[^\s&]+)', response.text)
            
            print(f"Top 5 raw matches for '{query}':")
            for m in matches[:5]:
                print(f"  - {m}")
                
            if matches:
                return matches[0]
    except Exception as e:
        print(f"Error: {e}")
    return None

def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    queries = [
        "PAPA FEEL 577",
        "FULI Electric Guasha",
        "Beleaf Liposomal Vitamin C"
    ]
    
    for q in queries:
        res = get_google_image_url(q)
        print(f"Selected: {res}\n")

if __name__ == "__main__":
    main()
