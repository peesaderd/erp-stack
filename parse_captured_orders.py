import json
import os
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    
    file_path = "captured_affiliate_orders.json"
    if not os.path.exists(file_path):
        print(f"{file_path} not found!")
        return
        
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    order_api_found = False
    
    for idx, item in enumerate(data):
        url = item['url']
        if "oec/pay/statement/order/seller/orders/list" in url:
            order_api_found = True
            print(f"\n[{idx}] Found Affiliate Orders List API Call:")
            print(f"URL: {url}")
            print(f"Status: {item['status']}")
            
            res_data = item['data']
            # Pretty print the json or a slice of it
            print("\nResponse Data:")
            print(json.dumps(res_data, indent=4, ensure_ascii=False))
            
    if not order_api_found:
        print("\nAffiliate Orders List API Call not found in captured responses.")
        # Print all URLs containing 'order' to help locate
        print("\nAll URLs containing 'order' or 'list':")
        for idx, item in enumerate(data):
            url = item['url']
            if "order" in url.lower() or "list" in url.lower():
                print(f"[{idx}] {url[:120]}")

if __name__ == "__main__":
    main()
