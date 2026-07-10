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
        
    found_api = False
    for idx, item in enumerate(data):
        url = item['url']
        if "promote_products/list" in url:
            found_api = True
            print(f"\n[{idx}] Found Open Collaboration Promote Products List API Call:")
            print(f"URL: {url}")
            res_data = item['data']
            print("\nResponse Data Keys:", list(res_data.keys()))
            if "data" in res_data:
                inner_data = res_data["data"]
                if isinstance(inner_data, dict):
                    print("Inner Data Keys:", list(inner_data.keys()))
                    if "products" in inner_data:
                        products = inner_data["products"]
                        print(f"Number of products found: {len(products)}")
                        for p_idx, prod in enumerate(products):
                            print(f"\nProduct {p_idx + 1}:")
                            print(f"  ID: {prod.get('product_id')}")
                            print(f"  Name: {prod.get('name')}")
                            print(f"  Price: {prod.get('price')}")
                            print(f"  Commission Rate: {prod.get('commission_rate')}%")
                            print(f"  Status: {prod.get('status')}")
                            # Print a few other fields if relevant
                    else:
                        print("No 'products' key in inner data.")
                else:
                    print("Inner data is not a dict:", type(inner_data))
            else:
                print("No 'data' key in response.")
                
    if not found_api:
        print("promote_products/list API Call not found in captured responses.")

if __name__ == "__main__":
    main()
