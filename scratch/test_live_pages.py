import urllib.request

req = urllib.request.Request('https://kidobits.m2igen.com/kidobits/theme/theme_phonicsLesson.html?lesson=L2.01', headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as resp:
    html = resp.read().decode('utf-8')
    print('L2.08 in LESSON_META:', 'Short i word family -ig' in html)
    print('L2 in client WORD_ALIASES:', '"big":' in html)
    print('playSentenceAudio word fallback:', 'playNextWord' in html)
