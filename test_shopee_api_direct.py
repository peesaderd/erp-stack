import os
import json
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def main():
    cookies_file = "shopee_cookies.json"
    if not os.path.exists(cookies_file):
        print(f"Error: {cookies_file} not found!")
        return
        
    with open(cookies_file, 'r', encoding='utf-8') as f:
        cookies_list = json.load(f)
        
    # Convert cookie list to a dictionary for requests library
    cookies_dict = {}
    for c in cookies_list:
        cookies_dict[c["name"]] = c["value"]
        
    # Prepare Shopee Search API URL
    # Search for "ครีมกันแดด"
    keyword = "ครีมกันแดด"
    url = "https://shopee.co.th/api/v4/search/search_items"
    
    params = {
        "by": "relevancy",
        "keyword": keyword,
        "limit": "10",
        "newest": "0",
        "order": "desc",
        "page_type": "search",
        "scenario": "PAGE_GLOBAL_SEARCH",
        "version": "2"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": f"https://shopee.co.th/search?keyword={requests.utils.quote(keyword)}",
        "x-api-source": "pc",
        "x-requested-with": "XMLHttpRequest",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }
    
    print(f"Sending direct GET request to Shopee Search API for keyword: '{keyword}'...")
    response = requests.get(url, params=params, headers=headers, cookies=cookies_dict, verify=False)
    
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Content-Type: {response.headers.get('Content-Type')}")
    
    try:
        data = response.json()
        print("Successfully parsed response as JSON!")
        
        # Check if there are search items in the response
        if "items" in data and data["items"]:
            print(f"Found {len(data['items'])} items in the search results:")
            for idx, item in enumerate(data["items"]):
                item_basic = item.get("item_basic", {})
                itemid = item_basic.get("itemid")
                shopid = item_basic.get("shopid")
                name = item_basic.get("name")
                price = item_basic.get("price")
                # Price is returned in micro-units (multiply by 100000)
                price_thb = price / 100000 if price else 0
                commission_rate = item_basic.get("commission_rate")
                
                print(f"{idx+1}. Name: {name}")
                print(f"   Item ID: {itemid} | Shop ID: {shopid}")
                print(f"   Price: {price_thb} THB")
                print(f"   Link: https://shopee.co.th/product-{shopid}-{itemid}")
        elif "error" in data:
            print(f"API returned error: {data['error']}")
            print(f"Response content: {response.text[:500]}")
        else:
            print("No items found or different JSON structure:")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        print(f"Response preview: {response.text[:1000]}")

if __name__ == "__main__":
    main()
