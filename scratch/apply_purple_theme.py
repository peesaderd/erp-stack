import paramiko
import re

print("Connecting to remote server...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')
sftp = ssh.open_sftp()

print("Reading remote theme_level3.html...")
with sftp.open('/var/www/kidobits/theme/theme_level3.html', 'r') as f:
    html = f.read().decode('utf-8')

# 1. Update CSS styles (glow, shadow, backgrounds)
html = html.replace('rgba(249, 115, 22, 0.2)', 'rgba(139, 124, 255, 0.22)')
html = html.replace('rgba(249, 115, 22, 0.3)', 'rgba(139, 124, 255, 0.3)')
html = html.replace('.glow-orange', '.glow-purple')
html = html.replace('#FFFBF5', '#FAF8FF')

# 2. Hero Banner Gradient & Text
html = html.replace(
    'bg-gradient-to-r from-orange-500 via-amber-500 to-amber-600',
    'bg-gradient-to-r from-[#8B7CFF] via-purple-600 to-indigo-600'
)
html = html.replace('border-orange-300', 'border-purple-200')
html = html.replace('text-orange-50', 'text-purple-100')
html = html.replace('text-orange-100', 'text-purple-200')
html = html.replace('text-orange-700', 'text-purple-700')
html = html.replace('text-orange-600', 'text-[#8B7CFF]')
html = html.replace('text-orange-800', 'text-purple-800')
html = html.replace('text-orange-900', 'text-purple-900')
html = html.replace('text-orange-950', 'text-purple-950')
html = html.replace('text-orange-300', 'text-purple-300')

# 3. Gradients and Accents
html = html.replace('from-orange-500 to-amber-500', 'from-[#8B7CFF] to-purple-600')
html = html.replace('hover:from-orange-600 hover:to-amber-600', 'hover:from-[#7A6AE6] hover:to-purple-700')
html = html.replace('from-amber-400 to-orange-500', 'from-[#B69CFF] to-[#8B7CFF]')
html = html.replace('from-orange-50 via-amber-50 to-orange-50', 'from-purple-50 via-violet-50 to-purple-50')
html = html.replace('from-orange-100 to-amber-50', 'from-purple-100 to-violet-50')

# 4. Backgrounds and Borders
html = html.replace('bg-orange-500', 'bg-[#8B7CFF]')
html = html.replace('hover:bg-orange-500', 'hover:bg-[#7A6AE6]')
html = html.replace('bg-orange-400', 'bg-[#9D8FFF]')
html = html.replace('bg-orange-100', 'bg-purple-100')
html = html.replace('bg-orange-50', 'bg-purple-50')
html = html.replace('hover:bg-orange-50', 'hover:bg-purple-50')
html = html.replace('hover:bg-orange-100', 'hover:bg-purple-100')
html = html.replace('hover:bg-orange-200', 'hover:bg-purple-100')

html = html.replace('border-orange-500', 'border-[#8B7CFF]')
html = html.replace('border-orange-600', 'border-[#7A6AE6]')
html = html.replace('border-orange-200', 'border-purple-200')
html = html.replace('border-orange-100', 'border-purple-100')
html = html.replace('hover:border-orange-400', 'hover:border-purple-400')
html = html.replace('hover:border-orange-500', 'hover:border-[#8B7CFF]')

html = html.replace('hover:text-orange-600', 'hover:text-[#8B7CFF]')
html = html.replace('shadow-orange-500/20', 'shadow-purple-500/20')
html = html.replace('shadow-orange-500/25', 'shadow-purple-500/25')
html = html.replace('shadow-orange-500', 'shadow-purple-500')
html = html.replace('selection:bg-orange-500', 'selection:bg-[#8B7CFF]')

# 5. Modal and Avatar Styling
html = html.replace('sm:border-orange-300', 'sm:border-purple-200')
html = html.replace('border-amber-300', 'border-purple-200')
html = html.replace('border-amber-600', 'border-purple-400')
html = html.replace('bg-amber-400', 'bg-purple-400')
html = html.replace('text-amber-900', 'text-purple-900')
html = html.replace('text-amber-950', 'text-purple-950')
html = html.replace('text-amber-800', 'text-purple-800')

# 6. Save and Push
print("Saving modified theme_level3.html to remote /tmp...")
with sftp.open('/tmp/theme_level3.html', 'w') as f:
    f.write(html)
sftp.close()

print("Applying to /var/www/kidobits/theme/theme_level3.html ...")
cmd = (
    "sudo cp /tmp/theme_level3.html /var/www/kidobits/theme/theme_level3.html && "
    "sudo chown www-data:www-data /var/www/kidobits/theme/theme_level3.html && "
    "cd /var/www/kidobits && "
    "git add theme/theme_level3.html && "
    "git commit -m 'style(theme_level3): change color theme from orange to signature Kidobits purple (#8B7CFF)' && "
    "git push origin main"
)

stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode())
print("STDERR:\n", stderr.read().decode())
ssh.close()
print("Done!")
