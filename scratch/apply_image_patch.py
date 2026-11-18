import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

patch_script = """
with open('/var/www/kidobits/theme/theme_phonicsLesson.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Step 1 with word image
old_step1_header = '''        box.innerHTML = `
          <p class="text-xs font-extrabold text-[#8B7CFF]">ขั้นที่ 1 • ผสมเสียง (แตะตามลำดับ ประกอบเป็นคำ)</p>
          <div class="mt-3 flex justify-center items-center gap-1">
            ${slotsHtml}
          </div>'''

new_step1_header = '''        box.innerHTML = `
          <p class="text-xs font-extrabold text-[#8B7CFF]">ขั้นที่ 1 • ผสมเสียง (แตะตามลำดับ ประกอบเป็นคำ)</p>
          <div class="my-2 flex justify-center">
            <div class="h-16 w-16 flex items-center justify-center">
              <img src="/kidobits/v2/images/${targetWord.toLowerCase().trim()}.png" alt="${targetWord}" class="h-16 w-16 object-contain drop-shadow-sm" onerror="this.style.display='none';" />
            </div>
          </div>
          <div class="mt-1 flex justify-center items-center gap-1">
            ${slotsHtml}
          </div>'''

assert old_step1_header in content, "old_step1_header not found"
content = content.replace(old_step1_header, new_step1_header)

# 2. Update Step 2 with word image
old_step2_header = '''        box.innerHTML = `
          <p class="text-xs font-extrabold text-[#8B7CFF]">ขั้นที่ 2 • เรียงตัวอักษรให้เป็นคำ</p>
          <div class="my-4">
            <button onclick="playTargetWord()" class="bg-[#FFC93C] text-black px-6 py-2.5 rounded-full font-extrabold text-sm shadow active:scale-95 transition">
              🔊 ฟังคำแล้วสะกด
            </button>
          </div>'''

new_step2_header = '''        box.innerHTML = `
          <p class="text-xs font-extrabold text-[#8B7CFF]">ขั้นที่ 2 • เรียงตัวอักษรให้เป็นคำ</p>
          <div class="my-2 flex justify-center">
            <div class="h-16 w-16 flex items-center justify-center">
              <img src="/kidobits/v2/images/${targetWord.toLowerCase().trim()}.png" alt="${targetWord}" class="h-16 w-16 object-contain drop-shadow-sm" onerror="this.style.display='none';" />
            </div>
          </div>
          <div class="my-2">
            <button onclick="playTargetWord()" class="bg-[#FFC93C] text-black px-6 py-2.5 rounded-full font-extrabold text-sm shadow active:scale-95 transition">
              🔊 ฟังคำแล้วสะกด
            </button>
          </div>'''

assert old_step2_header in content, "old_step2_header not found"
content = content.replace(old_step2_header, new_step2_header)

# 3. Update Step 3 (Listen & Choose) to show real illustration images
old_step3_btn = '''              return `
                <button onclick="submitAnswer('${w}')"
                        class="p-4 bg-[#FAF5FF] hover:bg-[#F3E8FF] border-2 border-[#E9D8FD] hover:border-[#8B7CFF] rounded-2xl flex flex-col items-center gap-1 active:scale-95 transition shadow-sm cursor-pointer">
                  <span class="text-3xl">${emoji}</span>
                  <span class="text-lg font-extrabold text-[#5B4B8A] mt-1">${w}</span>
                </button>
              `;'''

new_step3_btn = '''              return `
                <button onclick="submitAnswer('${w}')"
                        class="p-3 bg-[#FAF5FF] hover:bg-[#F3E8FF] border-2 border-[#E9D8FD] hover:border-[#8B7CFF] rounded-2xl flex flex-col items-center justify-between gap-1.5 active:scale-95 transition shadow-sm cursor-pointer min-h-[135px]">
                  <div class="h-16 w-16 flex items-center justify-center">
                    <img src="/kidobits/v2/images/${cleanW}.png" alt="${cleanW}" class="h-16 w-16 object-contain drop-shadow-sm" onerror="this.style.display='none'; if (this.nextElementSibling) this.nextElementSibling.style.display='block';" />
                    <span class="text-4xl" style="display:none;">${emoji}</span>
                  </div>
                  <span class="text-lg font-extrabold text-[#5B4B8A]">${w}</span>
                </button>
              `;'''

assert old_step3_btn in content, "old_step3_btn not found"
content = content.replace(old_step3_btn, new_step3_btn)

# 4. Update Step 4 (Independent Read) image URL and fallback
old_step4_box = '''        const cleanW = targetWord.toLowerCase().trim();
        const imgUrl = `/kidobits/v2/matsat/L1/${cleanW}.png`;
        const emoji = WORD_EMOJIS[cleanW] || '✨';

        box.innerHTML = `
          <p class="text-xs font-extrabold text-[#8B7CFF]">ขั้นที่ 4 • อ่านออกเสียงด้วยตัวเอง</p>
          <div class="p-6 bg-[#F5F1FF] rounded-2xl my-3 flex flex-col items-center">
            <img src="${imgUrl}" onerror="this.style.display='none'" class="h-20 w-20 object-contain mb-2 drop-shadow-sm" alt="${targetWord}" />
            <span class="text-5xl font-extrabold tracking-wider text-[#5B4B8A]">${targetWord}</span>
            <span class="text-xs font-bold text-[#7B7488] mt-2">คำที่ ${(currentItem.index || 0) + 1} จาก ${currentItem.total || 5}</span>
          </div>'''

new_step4_box = '''        const cleanW = targetWord.toLowerCase().trim();
        const imgUrl = `/kidobits/v2/images/${cleanW}.png`;
        const emoji = WORD_EMOJIS[cleanW] || '✨';

        box.innerHTML = `
          <p class="text-xs font-extrabold text-[#8B7CFF]">ขั้นที่ 4 • อ่านออกเสียงด้วยตัวเอง</p>
          <div class="p-6 bg-[#F5F1FF] rounded-2xl my-3 flex flex-col items-center">
            <div class="h-24 w-24 flex items-center justify-center mb-2">
              <img src="${imgUrl}" onerror="this.style.display='none'; if (this.nextElementSibling) this.nextElementSibling.style.display='block';" class="h-24 w-24 object-contain drop-shadow-sm" alt="${targetWord}" />
              <span class="text-5xl" style="display:none;">${emoji}</span>
            </div>
            <span class="text-5xl font-extrabold tracking-wider text-[#5B4B8A]">${targetWord}</span>
            <span class="text-xs font-bold text-[#7B7488] mt-2">คำที่ ${(currentItem.index || 0) + 1} จาก ${currentItem.total || 5}</span>
          </div>'''

assert old_step4_box in content, "old_step4_box not found"
content = content.replace(old_step4_box, new_step4_box)

with open('/tmp/theme_phonicsLesson_images.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCCESS: HTML updated with images")
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/patch_images.py', 'w') as f:
    f.write(patch_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/patch_images.py")
print("patch out:\n", stdout.read().decode())
print("patch err:\n", stderr.read().decode())

# Deploy to /var/www/kidobits/theme/theme_phonicsLesson.html
stdin, stdout, stderr = ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S cp /tmp/theme_phonicsLesson_images.html /var/www/kidobits/theme/theme_phonicsLesson.html")
print("cp:", stdout.read().decode(), stderr.read().decode())

ssh.close()
