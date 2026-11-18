from PIL import Image, ImageDraw
import numpy as np
import os

src_path = r'C:\Users\ADMIN\.gemini\antigravity\brain\00f15b47-0b14-4bb2-93bf-bae12846dfe6\new_pos_icon_raw_1794992067732.jpg'
out_dir = r'C:\Users\ADMIN\.gemini\antigravity\brain\00f15b47-0b14-4bb2-93bf-bae12846dfe6'

img = Image.open(src_path).convert('RGBA')

# Crop to squircle box with smooth radius
# Box: (135, 137, 886, 886)
# Center: 511, 511, size = 752
crop_box = (135, 136, 887, 888) # 752x752
cropped = img.crop(crop_box)

# Create squircle rounded mask
mask = Image.new('L', (752, 752), 0)
draw = ImageDraw.Draw(mask)
# Modern iOS squircle has ~22.5% radius = 170px
draw.rounded_rectangle([(0, 0), (752, 752)], radius=170, fill=255)

# Apply mask
cropped.putalpha(mask)

# 1. 512x512
icon_512 = cropped.resize((512, 512), Image.Resampling.LANCZOS)
icon_512.save(os.path.join(out_dir, 'pos-icon-512.png'), 'PNG')

# 2. 192x192
icon_192 = cropped.resize((192, 192), Image.Resampling.LANCZOS)
icon_192.save(os.path.join(out_dir, 'pos-icon-192.png'), 'PNG')

# 3. Maskable Icon (Centered with safe zone 80% size on dark blue bg)
maskable_bg = Image.new('RGBA', (512, 512), (17, 24, 39, 255)) # Dark navy #111827
# Paste icon in center at 410x410
inner_icon = icon_512.resize((410, 410), Image.Resampling.LANCZOS)
offset = (512 - 410) // 2
maskable_bg.paste(inner_icon, (offset, offset), inner_icon)
maskable_bg.save(os.path.join(out_dir, 'pos-icon-maskable-512.png'), 'PNG')

# 4. Favicon 64x64
favicon = cropped.resize((64, 64), Image.Resampling.LANCZOS)
favicon.save(os.path.join(out_dir, 'favicon.png'), 'PNG')

print("Generated PWA icons successfully!")
