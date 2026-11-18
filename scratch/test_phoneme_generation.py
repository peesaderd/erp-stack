import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

test_script = """
import asyncio
import edge_tts

async def gen():
    voice = "en-US-EmmaNeural"
    # Test 1: plain respelling
    await edge_tts.Communicate("shh", voice).save("/tmp/test_sh_respell.mp3")
    await edge_tts.Communicate("puh", voice).save("/tmp/test_p_respell.mp3")
    await edge_tts.Communicate("ih", voice).save("/tmp/test_i_respell.mp3")
    
    # Test 2: SSML with IPA if supported
    ssml_sh = '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US"><phoneme alphabet="ipa" ph="ʃ">sh</phoneme></speak>'
    try:
        await edge_tts.Communicate(ssml_sh, voice).save("/tmp/test_sh_ipa.mp3")
        print("SSML IPA succeeded!")
    except Exception as e:
        print("SSML IPA error:", e)

asyncio.run(gen())
print("Generation finished.")
"""

sftp = ssh.open_sftp()
with sftp.open('/tmp/test_phoneme_gen.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_phoneme_gen.py')
print("Output:", stdout.read().decode())
print("Error:", stderr.read().decode())

ssh.close()
