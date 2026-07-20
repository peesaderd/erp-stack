import csv

def main():
    path = "trending_affiliate_products.csv"
    with open(path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 15:
                break
            print(f"{i+1}: Name: {row.get('Product Name')} | Category: {row.get('Category')}")

if __name__ == "__main__":
    main()
