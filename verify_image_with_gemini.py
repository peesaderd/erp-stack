import os
import sys
import ssl
from google import genai
from PIL import Image
import urllib3

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Bypass SSL verification globally
    ssl._create_default_https_context = ssl._create_unverified_context
    
    # Load API Key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        env_paths = [os.path.abspath(".env"), os.path.expanduser("~/.env")]
        for p in env_paths:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("GEMINI_API_KEY="):
                            api_key = line.split("=", 1)[1].strip()
                            break
            if api_key:
                break
                
    if not api_key:
        print("Error: GEMINI_API_KEY not found.")
        sys.exit(1)
        
    import httpx
    from google.genai import types
    http_client = httpx.Client(verify=False)
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(httpxClient=http_client))
    
    image_path = "product_images/1729456727501474015.jpg"
    product_name = "PAPA FEEL 577 เซรั่มลดเลือนฝ้ากระและรอยสิว"
    
    if not os.path.exists(image_path):
        print(f"Error: Image {image_path} not found!")
        sys.exit(1)
        
    print(f"Opening image: {image_path}...")
    img = Image.open(image_path)
    
    prompt = f"""
    You are an asset quality inspector. Look at the attached image.
    We are selling the product: "{product_name}".
    Does this image show the actual product packaging, bottle, box, or tube for "{product_name}" (or closely related branding/product)?
    Reply YES if it is the correct product image.
    Reply NO if it is something else (like a pope, anime, person, generic landscape, or completely unrelated product).
    Also provide a 1-sentence reason.
    """
    
    print("Calling Gemini model...")
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[img, prompt]
    )
    
    print("\n--- Gemini Response ---")
    print(response.text)

if __name__ == "__main__":
    main()
