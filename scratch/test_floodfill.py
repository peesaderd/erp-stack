import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_code = r'''
from PIL import Image, ImageDraw

def remove_white_bg(img_path, out_path, thresh=40):
    im = Image.open(img_path).convert("RGBA")
    w, h = im.size
    
    # Check 4 corners
    corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]
    
    # We want to replace connected near-white background with transparent (0, 0, 0, 0)
    for c in corners:
        px = im.getpixel(c)
        # check if corner is near white (R,G,B > 220)
        if px[0] > 220 and px[1] > 220 and px[2] > 220:
            ImageDraw.floodfill(im, c, (0, 0, 0, 0), thresh=thresh)
            
    im.save(out_path, "PNG")
    print(f"Saved {out_path} with extrema:", im.getextrema())

remove_white_bg('/var/www/kidobits/v2/images/wig.png', '/tmp/wig_transparent.png')
remove_white_bg('/var/www/kidobits/v2/images/elephant.png', '/tmp/elephant_transparent.png')
remove_white_bg('/var/www/kidobits/v2/images/jet.png', '/tmp/jet_transparent.png')
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_floodfill.py', 'w') as f:
    f.write(remote_code)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_floodfill.py')
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("ERR:", err)

ssh.close()
