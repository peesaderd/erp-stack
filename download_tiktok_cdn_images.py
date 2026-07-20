import requests
import urllib3

def download_file(url, path):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = requests.get(url, headers=headers, verify=False, timeout=10)
        if r.status_code == 200:
            with open(path, "wb") as f:
                f.write(r.content)
            print(f"Downloaded: {path}")
        else:
            print(f"Failed to download {url}: {r.status_code}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    download_file(
        "https://p16-oec-sg.ibyteimg.com/tos-alisg-i-aphluv4xwc-sg/bff87fbdad184741a67fdfbb42d31f71~tplv-aphluv4xwc-origin-jpeg.jpeg",
        "tiktok_img1.jpeg"
    )
    download_file(
        "https://p16-oec-sg.ibyteimg.com/tos-alisg-i-aphluv4xwc-sg/a3e07e282b1b4308a4666c7233f70f18~tplv-aphluv4xwc-origin-png.png",
        "tiktok_img2.png"
    )

if __name__ == "__main__":
    main()
