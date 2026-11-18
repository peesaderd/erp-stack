with open('scratch/PosRestodash.vue', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the bottom nav block
nav_start = content.find('<!-- ── MOBILE BOTTOM NAVIGATION BAR (PWA UX) ───────────────────── -->')
nav_end = content.find('</nav>', nav_start) + len('</nav>')
nav_block = content[nav_start:nav_end].strip()

# Remove it from its current position
content_without_nav = content[:nav_start] + content[nav_end:]

# Now find the closing </div> of .pos-restodash
# It is right after the toast transition
toast_end = content_without_nav.find('</transition>', content_without_nav.find('pos-toast'))
assert toast_end != -1, "toast transition not found!"
div_close = content_without_nav.find('</div>', toast_end)
assert div_close != -1, "closing </div> not found!"

# Insert nav_block right before div_close
final_content = content_without_nav[:div_close] + '\n\n    ' + nav_block + '\n\n  ' + content_without_nav[div_close:]

with open('scratch/PosRestodash.vue', 'w', encoding='utf-8') as f:
    f.write(final_content)

print("Moved pos-mobile-bottom-nav inside .pos-restodash successfully!")
