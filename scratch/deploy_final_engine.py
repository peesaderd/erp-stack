import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = r'''
with open("/var/www/kidobits/js/kb-az-engine.js", "r", encoding="utf-8") as f:
    orig = f.read()

# Backup current kb-az-engine.js
with open("/tmp/kb-az-engine-pre-hybrid.js", "w", encoding="utf-8") as f:
    f.write(orig)

# Read extracted logic
with open("/tmp/extracted_logic.js", "r", encoding="utf-8") as f:
    extracted = f.read()

# Build the complete, clean kb-az-engine.js
new_engine = r'''/**
 * Kidobits A-Z Player Audio & Speech Engine (Hybrid Web Speech + Fallback)
 * Lifted cleanly from english.html architecture:
 * 1. Native Chrome SpeechRecognition for zero-locking, instant auto-cut when speaking stops
 * 2. Complete phonicsKeywords dictionary & checkPhonicsMatch matching logic
 * 3. Server STT fallback for non-supported browsers
 */
(function() {
  'use strict';

  var PRAISES = [
    '/kidobits/audio/praise_perfect_1.mp3',
    '/kidobits/audio/praise_perfect_2.mp3',
    '/kidobits/audio/praise_good_1.mp3',
    '/kidobits/audio/praise_good_2.mp3',
    '/kidobits/audio/praise_1.mp3',
    '/kidobits/audio/praise_2.mp3',
    '/kidobits/audio/praise_3.mp3',
    '/kidobits/audio/praise_4.mp3'
  ];

  // Full dictionary from english.html
  var phonicsKeywords = {
    'A': ['apple', 'apples', 'แอะ', 'แอปเปิ้ล', 'a', 'เอ'],
    'B': ['ball', 'balls', 'บอล', 'เบอะ', 'b', 'บี'],
    'C': ['cat', 'cats', 'cut', 'cap', 'cab', 'แคท', 'เคอะ', 'c', 'ซี'],
    'D': ['dog', 'dogs', 'dock', 'dot', 'duck', 'ด็อก', 'เดอะ', 'd', 'ดี'],
    'E': ['egg', 'eggs', 'เอ้ก', 'เอะ', 'e', 'อี'],
    'F': ['fish', 'fishes', 'fit', 'fin', 'finish', 'ฟิช', 'เฟอะ', 'f', 'เอฟ'],
    'G': ['goat', 'goats', 'got', 'good', 'go', 'goal', 'โกท', 'เกอะ', 'g', 'จี'],
    'H': ['hat', 'hats', 'had', 'has', 'hit', 'hot', 'hut', 'แฮท', 'เฮอะ', 'h', 'เอช'],
    'I': ['insect', 'insects', 'inside', 'into', 'อินเซก', 'อิ', 'i', 'ไอ'],
    'J': ['jam', 'jams', 'jump', 'jan', 'แยม', 'เจอะ', 'j', 'เจ'],
    'K': ['kite', 'kites', 'kind', 'keen', 'key', 'ไคท์', 'เคอะ', 'k', 'เค'],
    'L': ['log', 'logs', 'lock', 'locks', 'lot', 'long', 'lost', 'love', 'ล็อก', 'เลอะ', 'l', 'แอล'],
    'M': ['moon', 'moons', 'mom', 'more', 'move', 'mood', 'man', 'มูน', 'เมอะ', 'm', 'เอ็ม'],
    'N': ['net', 'nets', 'next', 'neck', 'need', 'nest', 'not', 'nut', 'เน็ต', 'เนอะ', 'n', 'เอ็น'],
    'O': ['octopus', 'october', 'off', 'on', 'เอาะ', 'อ็อกโทพุส', 'o', 'โอ'],
    'P': ['pig', 'pigs', 'pick', 'picks', 'pic', 'pink', 'peak', 'peek', 'พิก', 'เพอะ', 'p', 'พี'],
    'Q': ['queen', 'queens', 'quick', 'quin', 'keen', 'kwuh', 'ควีน', 'ควะ', 'q', 'คิว'],
    'R': ['robot', 'robots', 'rob', 'road', 'rabbit', 'โรบอท', 'เรอะ', 'r', 'อาร์'],
    'S': ['sun', 'suns', 'son', 'some', 'summer', 'ซัน', 'เซอะ', 's', 'เอส'],
    'T': ['tiger', 'tigers', 'tight', 'time', 'ไทเกอร์', 'เทอะ', 't', 'ที'],
    'U': ['umbrella', 'umbrellas', 'under', 'up', 'อัมเบรลลา', 'อะ', 'u', 'ยู'],
    'V': ['van', 'vans', 'fan', 'แวน', 'เวอะ', 'v', 'วี'],
    'W': ['watch', 'watches', 'water', 'wash', 'วอทช์', 'เวอะ', 'w', 'ดับเบิลยู'],
    'X': ['box', 'boxes', 'fox', 'six', 'บ็อกซ์', 'คซ', 'x', 'เอ็กซ์'],
    'Y': ['yak', 'yaks', 'yes', 'yeah', 'ยัค', 'เยอะ', 'y', 'วาย'],
    'Z': ['zebra', 'zebras', 'zoo', 'zip', 'ม้าลาย', 'ซีบรา', 'เซอะ', 'z', 'แซด', 'ซี']
  };

  var PHONICS_WORDS = {
    'A': 'apple', 'B': 'ball', 'C': 'cat', 'D': 'dog', 'E': 'egg',
    'F': 'fish', 'G': 'goat', 'H': 'hat', 'I': 'insect', 'J': 'jam',
    'K': 'kite', 'L': 'log', 'M': 'moon', 'N': 'net', 'O': 'octopus',
    'P': 'pig', 'Q': 'queen', 'R': 'robot', 'S': 'sun', 'T': 'tiger',
    'U': 'umbrella', 'V': 'van', 'W': 'watch', 'X': 'box', 'Y': 'yak', 'Z': 'zebra'
  };

  function checkPhonicsMatch(spoken, letter) {
    if (!spoken || !letter) return null;
    spoken = spoken.toLowerCase().replace(/[^a-z0-9\u0E00-\u0E7F ]/g, ' ').trim();
    var targetWord = (PHONICS_WORDS[letter] || '').toLowerCase().trim();
    var targetLetter = letter.toLowerCase().trim();

    // 1. Direct word or letter match
    if (spoken === targetWord || spoken === targetLetter) return targetWord;

    // 2. Token match
    var tokens = spoken.split(/\s+/).filter(Boolean);
    if (tokens.includes(targetWord) || tokens.includes(targetLetter)) return targetWord;

    // 3. Accepted keywords dictionary match
    var accepted = phonicsKeywords[letter] || [targetWord];
    for (var i = 0; i < accepted.length; i++) {
      var lowKw = accepted[i].toLowerCase().trim();
      if (!lowKw) continue;
      if (tokens.includes(lowKw) || spoken.includes(lowKw)) return accepted[i];
    }

    // 4. Starts with prefix match (for words >= 4 chars)
    if (targetWord.length >= 4) {
      for (var j = 0; j < tokens.length; j++) {
        var t = tokens[j];
        if (t.length >= 3 && t.indexOf(targetWord.slice(0, 3)) === 0) return targetWord;
      }
    }
    return null;
  }

  var AudioMgr = {
    currentAudio: null,
    unlocked: false,
    unlock: function() {
      if (this.unlocked) return;
      this.unlocked = true;
      try {
        var silent = new Audio('data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA');
        silent.play().catch(function() {});
      } catch (e) {}
    },
    stop: function() {
      if (this.currentAudio) {
        try {
          this.currentAudio.pause();
          this.currentAudio.currentTime = 0;
          this.currentAudio.onended = null;
          this.currentAudio.onerror = null;
        } catch (e) {}
        this.currentAudio = null;
      }
    },
    play: function(url, onEnded, onBlocked) {
      this.stop();
      this.unlock();
      var a = new Audio(url);
      this.currentAudio = a;
      var endedCalled = false;
      function done() {
        if (endedCalled) return;
        endedCalled = true;
        if (onEnded) onEnded();
      }
      a.onended = done;
      a.onerror = done;
      var p = a.play();
      if (p && p.catch) {
        p.catch(function(err) {
          console.warn('[AudioMgr] Play blocked:', err);
          if (onBlocked) onBlocked(err);
        });
      }
    }
  };

  window.addEventListener('pointerdown', function() { AudioMgr.unlock(); }, { capture: true, passive: true });
  window.addEventListener('click', function() { AudioMgr.unlock(); }, { capture: true, passive: true });

  var currentLetter = null;
  var isListening = false;
  var nativeRec = null;
  var serverStream = null;
  var serverRec = null;
  var autoAdvanceTimer = null;
  var safetyTimeout = null;

  function isAZScreen() {
    if (!document.body) return false;
    var t = document.body.innerText || '';
    return t.includes('สอนโฟนิกส์ • ตัวอักษร') || t.includes('EMMA A-Z PHONICS MONITOR');
  }

  function detectCurrentLetter() {
    if (!isAZScreen()) return null;
    var match = document.body ? document.body.innerText.match(/ตัวอักษร\s*([A-Z])/i) : null;
    if (match) return match[1].toUpperCase();
    var match2 = document.body ? document.body.innerText.match(/([A-Z])([a-z])\s*•/) : null;
    if (match2) return match2[1].toUpperCase();
    return null;
  }

  function updateMicVisuals(vol, text) {
    if (!isAZScreen()) return;
    var bars = document.querySelectorAll('div.bg-\\[\\#FF5B6A\\].rounded-full');
    bars.forEach(function(bar) {
      if (bar.style) bar.style.width = Math.min(100, Math.max(0, vol)) + '%';
    });

    var pTags = Array.from(document.querySelectorAll('p'));
    var volP = pTags.find(function(p) { return p.innerText.includes('ระดับเสียงไมค์:'); });
    if (volP) {
      volP.innerText = 'ระดับเสียงไมค์: ' + Math.round(vol) + '%';
    }

    if (text) {
      var feedbackP = pTags.find(function(p) {
        return p.className.includes('font-bold') && p.className.includes('text-sm') && !p.innerText.includes('ระดับเสียงไมค์');
      });
      if (feedbackP) {
        feedbackP.innerText = text;
      }
    }
  }

  function stopMic() {
    isListening = false;
    if (safetyTimeout) { clearTimeout(safetyTimeout); safetyTimeout = null; }

    if (nativeRec) {
      try {
        nativeRec.onresult = null;
        nativeRec.onend = null;
        nativeRec.onerror = null;
        nativeRec.abort();
      } catch (e) {}
      nativeRec = null;
    }

    if (serverStream) {
      try { serverStream.getTracks().forEach(function(t) { t.stop(); }); } catch (e) {}
      serverStream = null;
    }

    if (serverRec && serverRec.state !== 'inactive') {
      try { serverRec.stop(); } catch (e) {}
    }
    serverRec = null;

    updateMicVisuals(0);
  }

  function handleSuccess(letter, text) {
    stopMic();
    var word = PHONICS_WORDS[letter] || letter;
    updateMicVisuals(0, 'เก่งมาก! พูดว่า “' + (text || word) + '” 🎉 ถูกต้องค่ะ!');

    var praise = PRAISES[Math.floor(Math.random() * PRAISES.length)];
    AudioMgr.play(praise, function() {
      if (autoAdvanceTimer) clearTimeout(autoAdvanceTimer);
      autoAdvanceTimer = setTimeout(function() {
        if (!isAZScreen()) return;
        var nextBtn = Array.from(document.querySelectorAll('button')).find(function(b) {
          return b.innerText.includes('Next');
        });
        if (nextBtn && !nextBtn.disabled) {
          nextBtn.click();
        }
      }, 700);
    });
  }

  function startMic(targetLetter) {
    if (!isAZScreen() || !targetLetter) return;
    stopMic();
    isListening = true;

    var word = PHONICS_WORDS[targetLetter] || targetLetter;
    updateMicVisuals(10, 'ครูเอ็มม่ากำลังฟัง... พูดคำว่า “' + word + '” ได้เลยค่ะ 🎙️');

    var SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition || null;

    // 1. DESKTOP / CHROME NATIVE SPEECH (Auto cut, zero mic locking)
    if (SpeechRec) {
      try {
        var rec = new SpeechRec();
        rec.lang = 'en-US';
        rec.continuous = false; // Cuts immediately when user stops speaking!
        rec.interimResults = true;
        rec.maxAlternatives = 5;

        rec.onaudiostart = function() { updateMicVisuals(40); };
        rec.onspeechstart = function() { updateMicVisuals(80); };
        rec.onspeechend = function() {
          // Hardware mic turns off here!
          updateMicVisuals(10, 'กำลังตรวจเสียงอ่าน... ✨');
        };
        rec.onaudioend = function() { updateMicVisuals(0); };

        rec.onresult = function(event) {
          if (!isListening) return;
          var spoken = '';
          var isFinal = false;
          for (var i = event.resultIndex; i < event.results.length; ++i) {
            var res = event.results[i];
            if (res.isFinal) isFinal = true;
            for (var a = 0; a < res.length; a++) {
              spoken = (res[a].transcript || '').toLowerCase().trim();
              var match = checkPhonicsMatch(spoken, targetLetter);
              if (match) {
                handleSuccess(targetLetter, match);
                return;
              }
            }
          }
          if (isFinal) {
            stopMic();
            updateMicVisuals(0, 'ได้ยิน: “' + spoken + '” (แตะไมค์ 🎙️ ลองใหม่อีกรอบนะคนเก่ง)');
          }
        };

        rec.onerror = function(e) {
          console.warn('Native SpeechRec error:', e);
          if (e.error === 'network' || e.error === 'audio-capture') {
            startServerFallback(targetLetter);
          } else {
            stopMic();
            updateMicVisuals(0, 'แตะไมค์ 🎙️ เพื่อลองพูดใหม่นะคะ');
          }
        };

        rec.onend = function() {
          if (isListening) {
            stopMic();
          }
        };

        nativeRec = rec;
        rec.start();

        safetyTimeout = setTimeout(function() {
          if (isListening) {
            stopMic();
            updateMicVisuals(0, 'แตะไมค์ 🎙️ เพื่อลองพูดอีกครั้งนะคะ');
          }
        }, 6000);
        return;
      } catch (err) {
        console.warn('Native speech failed, fallback to server:', err);
      }
    }

    // 2. FALLBACK FOR BROWSERS WITHOUT SPEECHRECOGNITION
    startServerFallback(targetLetter);
  }

  function startServerFallback(targetLetter) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      stopMic();
      updateMicVisuals(0, 'บราวเซอร์ไม่รองรับการบันทึกเสียง');
      return;
    }

    navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
      .then(function(stream) {
        if (!isListening || currentLetter !== targetLetter) {
          stream.getTracks().forEach(function(t) { t.stop(); });
          return;
        }
        serverStream = stream;
        var mr = new MediaRecorder(stream);
        serverRec = mr;
        var chunks = [];

        mr.ondataavailable = function(e) {
          if (e.data && e.data.size > 0) chunks.push(e.data);
        };

        mr.onstop = function() {
          if (serverStream) {
            serverStream.getTracks().forEach(function(t) { t.stop(); });
            serverStream = null;
          }
          if (chunks.length === 0) { stopMic(); return; }

          var blob = new Blob(chunks, { type: 'audio/webm' });
          var fd = new FormData();
          fd.append('audio', blob, 'child.webm');
          var word = PHONICS_WORDS[targetLetter] || targetLetter;
          fd.append('hint', (phonicsKeywords[targetLetter] || [word]).join(','));

          updateMicVisuals(25, 'กำลังตรวจเสียงอ่าน... ✨');
          fetch('/kidobits/stt', { method: 'POST', body: fd })
            .then(function(r) { return r.json(); })
            .then(function(data) {
              var spoken = (data && (data.text || data.transcript || '')) || '';
              var match = checkPhonicsMatch(spoken, targetLetter);
              if (match || (data && data.fuzzy_ok)) {
                handleSuccess(targetLetter, match || word);
              } else {
                stopMic();
                updateMicVisuals(0, 'ได้ยิน: “' + spoken + '” (แตะไมค์ 🎙️ ลองใหม่อีกรอบนะคนเก่ง)');
              }
            })
            .catch(function() {
              stopMic();
              updateMicVisuals(0, 'แตะไมค์ 🎙️ เพื่อลองพูดอีกครั้งนะคะ');
            });
        };

        mr.start();
        safetyTimeout = setTimeout(function() {
          if (isListening && serverRec && serverRec.state === 'recording') {
            serverRec.stop();
          }
        }, 3000);
      })
      .catch(function() {
        stopMic();
        updateMicVisuals(0, 'กรุณาแตะอนุญาตไมโครโฟนนะคะ 🎙️');
      });
  }

  function onLetterChanged(newLetter) {
    if (!isAZScreen() || !newLetter || newLetter === currentLetter) return;
    currentLetter = newLetter;

    stopMic();
    if (autoAdvanceTimer) {
      clearTimeout(autoAdvanceTimer);
      autoAdvanceTimer = null;
    }

    var audioUrl = '/kidobits/audio/' + newLetter + '.mp3';
    updateMicVisuals(0, 'ครูเอ็มม่ากำลังสอนนำ: ' + newLetter + ' ... 🔊');

    AudioMgr.play(audioUrl, function() {
      setTimeout(function() {
        if (isAZScreen() && currentLetter === newLetter) {
          startMic(newLetter);
        }
      }, 300);
    }, function() {
      updateMicVisuals(0, 'แตะ 🔊 ฟังเสียง เพื่อฟังครูเอ็มม่าสอนนำนะคะ');
    });
  }

  window.triggerAZMic = function() {
    var letter = detectCurrentLetter();
    if (!letter) return;
    if (isListening) {
      stopMic();
      updateMicVisuals(0, 'หยุดไมค์แล้ว แตะเพื่อเริ่มใหม่');
    } else {
      startMic(letter);
    }
  };

  document.addEventListener('click', function(e) {
    var target = e.target;
    var btn = target.closest ? target.closest('button') : null;
    if (!btn) return;

    var text = btn.innerText.trim();

    if (text.includes('← บทเรียน') || btn.closest('nav')) {
      stopMic();
      AudioMgr.stop();
      currentLetter = null;
      return;
    }

    if (!isAZScreen()) return;

    if (text.includes('ฟังเสียง') || text.includes('🔊')) {
      var letter = detectCurrentLetter();
      if (letter) {
        var audioUrl = '/kidobits/audio/' + letter + '.mp3';
        AudioMgr.play(audioUrl, function() {
          setTimeout(function() {
            if (isAZScreen() && currentLetter === letter) {
              startMic(letter);
            }
          }, 300);
        });
      }
      return;
    }

    if (btn.className.includes('bg-[#FF5B6A]') && text.includes('🎙️')) {
      e.stopPropagation();
      window.triggerAZMic();
      return;
    }

    if (text.length === 1 && text >= 'A' && text <= 'Z') {
      setTimeout(function() {
        var letter = detectCurrentLetter();
        if (letter && letter !== currentLetter) {
          onLetterChanged(letter);
        }
      }, 50);
      return;
    }

    if (text.includes('Next') || text.includes('Prev')) {
      setTimeout(function() {
        var letter = detectCurrentLetter();
        if (letter && letter !== currentLetter) {
          onLetterChanged(letter);
        }
      }, 50);
      return;
    }
  }, true);

  setInterval(function() {
    if (!isAZScreen()) {
      if (currentLetter !== null) {
        currentLetter = null;
        stopMic();
        AudioMgr.stop();
      }
      return;
    }
    var letter = detectCurrentLetter();
    if (letter && letter !== currentLetter) {
      onLetterChanged(letter);
    }
  }, 400);

})();
'''

with open("/tmp/kb-az-engine-clean-final.js", "w", encoding="utf-8") as f:
    f.write(new_engine)
print("Saved /tmp/kb-az-engine-clean-final.js")
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/build_final_engine.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/build_final_engine.py')
print(stdout.read().decode())
print("ERR:", stderr.read().decode())

# Deploy to kb-az-engine.js with sudo
cmd = 'echo "OpenHands@ERP2026" | sudo -S cp /tmp/kb-az-engine-clean-final.js /var/www/kidobits/js/kb-az-engine.js && echo "DEPLOY_FINAL_OK"'
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())

# Update cache buster in theme_azPlayer.html
cmd2 = 'echo "OpenHands@ERP2026" | sudo -S sed -i "s/kb-az-engine.js?v=[^\"]*/kb-az-engine.js?v=20261114_native_final/g" /var/www/kidobits/theme/theme_azPlayer.html'
stdin, stdout, stderr = ssh.exec_command(cmd2)
print(stdout.read().decode())

ssh.close()
