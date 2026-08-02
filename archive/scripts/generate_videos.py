import os
import sys
import json
import asyncio
import edge_tts
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

# Configure encoding for Windows console output
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

async def generate_voiceover(text, output_path):
    """Generate Thai neural voiceover using edge-tts."""
    print(f"Generating voiceover: '{text[:50]}...'")
    # th-TH-PremwadeeNeural is a high-quality female Thai voice
    voice = "th-TH-PremwadeeNeural"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)
    print(f"Saved voiceover to: {output_path}")

def download_product_image(profile_dir, product_url, output_image_path):
    """Download main product image or capture element screenshot using Playwright."""
    print(f"Loading product page to capture image: {product_url}")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_viewport_size({"width": 800, "height": 800})
        
        try:
            # Navigate to product page
            page.goto(product_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(8000)
            
            # Look for product image carousel or main image elements
            # Common TikTok Shop product page image class names or tags
            img_selector = "div[class*='carousel'] img, img[class*='main'], img[src*='tos-alisg'], div[class*='image'] img"
            img_element = page.locator(img_selector).first
            
            if img_element.is_visible():
                print("Found main product image element! Taking screenshot of element...")
                img_element.screenshot(path=output_image_path)
                print(f"Saved product image: {output_image_path}")
            else:
                # Fallback: take a screenshot of the main visible area
                print("Main image element not found. Taking page screenshot as fallback...")
                page.screenshot(path=output_image_path)
                print(f"Saved fallback page screenshot: {output_image_path}")
                
        except Exception as e:
            print(f"Error capturing image: {e}")
            # Final fallback: create a solid color background image
            img = Image.new('RGB', (800, 800), color=(254, 44, 85)) # TikTok Pink
            img.save(output_image_path)
            print(f"Created fallback background color image: {output_image_path}")
            
        context.close()

def create_subtitle_frame(base_image_path, text, output_path):
    """Draw a styled semi-transparent subtitle banner over the image using Pillow."""
    img = Image.open(base_image_path)
    img = img.resize((800, 800)) # Standardize size
    draw = ImageDraw.Draw(img, "RGBA")
    
    # Define text banner dimensions
    banner_height = 120
    banner_y = 800 - banner_height - 50 # Position near the bottom
    
    # Draw semi-transparent black rectangle banner
    draw.rectangle(
        [(40, banner_y), (760, banner_y + banner_height)],
        fill=(0, 0, 0, 180) # Black with 180 alpha
    )
    
    # Try to load a clean font, fallback to default
    try:
        # Segoe UI or Arial or Tahoma
        font_path = "C:\\Windows\\Fonts\\tahoma.ttf" # standard Thai font in Windows
        if not os.path.exists(font_path):
            font_path = "C:\\Windows\\Fonts\\arial.ttf"
        font = ImageFont.truetype(font_path, 28)
    except IOError:
        font = ImageFont.load_default()
        
    # Split text into two lines if it's too long
    words = text.split(" ")
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        # Check text length
        test_str = " ".join(current_line)
        # In newer Pillow version, draw.textlength is available
        try:
            w = draw.textlength(test_str, font=font)
        except AttributeError:
            w = len(test_str) * 14 # rough estimation
            
        if w > 680:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
        
    # Draw text lines centered in the banner
    y_offset = banner_y + 15
    for line in lines[:2]: # Max 2 lines
        try:
            w = draw.textlength(line, font=font)
        except AttributeError:
            w = len(line) * 14
            
        text_x = 400 - (w / 2) # Center horizontally
        draw.text((text_x, y_offset), line, fill=(255, 255, 255, 255), font=font) # White text
        y_offset += 40
        
    img.save(output_path)

def render_product_video(product, profile_dir):
    """Assemble the video file from generated voiceover, product images, and subtitles."""
    pid = product["product_id"]
    name = product["product_name"]
    scripts = product["ai_scripts"]
    voiceover_text = scripts["voiceover"]
    timeline = scripts["visual_timeline"]
    product_url = product["product_url"]
    
    print(f"\n==========================================")
    print(f"Generating video for: {name} (ID: {pid})")
    print(f"==========================================")
    
    # Create output directories
    os.makedirs("images", exist_ok=True)
    os.makedirs("videos", exist_ok=True)
    
    # File Paths
    base_image = f"images/base_{pid}.png"
    voiceover_mp3 = f"videos/temp_{pid}.mp3"
    output_mp4 = f"videos/product_{pid}.mp4"
    
    # 1. Download/capture product base image
    download_product_image(profile_dir, product_url, base_image)
    
    # 2. Generate Voiceover TTS
    asyncio.run(generate_voiceover(voiceover_text, voiceover_mp3))
    
    # 3. Create video clips matching the timeline
    audio_clip = AudioFileClip(voiceover_mp3)
    total_audio_duration = audio_clip.duration
    print(f"Total audio duration: {total_audio_duration:.2f} seconds")
    
    # We split the audio into proportional segments matching the visual timeline
    # E.g. timeline items have time ranges like "0-3s", "3-8s", "8-18s", "18-25s"
    # We parse the percentage durations of each segment to align them perfectly.
    clips = []
    
    segment_durations = []
    for step in timeline:
        t_range = step["time"].replace("s", "").split("-")
        start = float(t_range[0])
        end = float(t_range[1])
        segment_durations.append(end - start)
        
    total_timeline_duration = sum(segment_durations)
    
    # Build frames with text overlays
    current_time = 0.0
    for idx, step in enumerate(timeline):
        action = step["action"]
        # Scale the segment duration proportionally to fit the actual audio duration
        duration_ratio = segment_durations[idx] / total_timeline_duration
        seg_duration = duration_ratio * total_audio_duration
        
        frame_img_path = f"images/frame_{pid}_{idx}.png"
        
        # Display the voiceover text corresponding to this step
        # Since voiceover text is a single paragraph, we show progressive parts or the main hook
        subtitle_text = action
        if idx == 0:
            subtitle_text = f"🔥 {scripts.get('hook', name)}"
        elif idx == len(timeline) - 1:
            subtitle_text = "👇 สั่งซื้อด่วนตรงตะกร้าเหลืองซ้ายล่าง!"
            
        create_subtitle_frame(base_image, subtitle_text, frame_img_path)
        
        # Create image clip for this duration
        clip = ImageClip(frame_img_path).set_duration(seg_duration)
        clips.append(clip)
        current_time += seg_duration
        
    # Concatenate clips and overlay audio
    video_clip = concatenate_videoclips(clips, method="compose")
    video_clip = video_clip.set_audio(audio_clip)
    
    # Write the output file
    print(f"Writing video file to: {output_mp4}...")
    video_clip.write_videofile(
        output_mp4,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None # Suppress verbose progress output
    )
    
    # Close resources to release locks
    audio_clip.close()
    video_clip.close()
    
    # Cleanup temporary frames
    try:
        os.remove(voiceover_mp3)
        for idx in range(len(timeline)):
            os.remove(f"images/frame_{pid}_{idx}.png")
    except Exception:
        pass
        
    print(f"SUCCESS: Generated video: {output_mp4}")
    return output_mp4

def main():
    profile_dir = os.path.abspath(".tiktok_profile")
    
    # Load JSON catalog containing scripts
    json_path = "video_scripts_data_tiktok.json"
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found. Please run generate_video_scripts_tiktok.py first.")
        sys.exit(1)
        
    with open(json_path, "r", encoding="utf-8") as f:
        products = json.load(f)
        
    print(f"Loaded {len(products)} products from catalog.")
    
    # For demonstration, generate video for the top product
    if products:
        top_product = products[0]
        render_product_video(top_product, profile_dir)
        
if __name__ == "__main__":
    main()
