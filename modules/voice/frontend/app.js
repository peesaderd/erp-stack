class VoicePOS {
  constructor() {
    this.recognition = null;
    this.synthesis = window.speechSynthesis;
    this.isRecording = false;
    this.conversationHistory = [];
    this.currentOrder = [];
    this.finalTranscript = '';
    this.pendingItems = [];
    this._silenceTimer = null;
    this._silenceTimeout = 3000;
    this._isSpeaking = false;
    this._processing = false;       // prevent double-fire
    this._restartQueued = false;
    this._recognitionReady = false;

    this.init();
  }

  init() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('เบราว์เซอร์นี้ไม่รองรับ Voice Recognition\nกรุณาใช้ Chrome หรือ Edge');
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.recognition = new SpeechRecognition();
    this.recognition.lang = 'th-TH';
    this.recognition.continuous = true;
    this.recognition.interimResults = true;
    this.recognition.maxAlternatives = 1;

    this.recognition.onstart = () => {
      this._recognitionReady = true;
      this.isRecording = true;
      this.updateUI();
    };

    this.recognition.onresult = (event) => {
      // Only process new results from event.resultIndex onward
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0].transcript;
        if (result.isFinal) {
          // Deduplicate: only add if different from what we have
          const trimmed = transcript.trim();
          if (trimmed && !this.finalTranscript.endsWith(trimmed)) {
            this.finalTranscript += (this.finalTranscript ? ' ' : '') + trimmed;
          }
          this._resetSilenceTimer();
        }
      }
    };

    this.recognition.onerror = (event) => {
      console.warn('Speech error:', event.error);
      // no-speech and aborted are NORMAL — do NOT restart, just ignore
      // The browser will keep the recognition session alive
      if (event.error === 'not-allowed') {
        this.setStatus('กรุณาเปิดอนุญาตไมโครโฟน', 'error');
        this.isRecording = false;
        this._recognitionReady = false;
        this.updateUI();
      }
      // network and service-not-available are real errors — restart once
      if ((event.error === 'network' || event.error === 'service-not-available') && this.isRecording && !this._processing) {
        this._safeRestart();
      }
    };

    this.recognition.onend = () => {
      this._recognitionReady = false;
      // Auto-restart silently — no UI flicker, no delay
      if (this.isRecording && !this._processing && !this._isSpeaking) {
        setTimeout(() => {
          if (this.isRecording && !this._processing && !this._isSpeaking) {
            try { this.recognition.start(); } catch(e) {}
          }
        }, 100);
      }
    };

    // Button handlers
    document.getElementById('micBtn').addEventListener('click', () => this.toggleRecording());
    document.getElementById('clearBtn').addEventListener('click', () => this.clearChat());
    document.getElementById('btnAddCart').addEventListener('click', () => this.confirmAddToCart());
    document.getElementById('btnSkip').addEventListener('click', () => this.skipItems());
    document.getElementById('btnSendKitchen').addEventListener('click', () => this.finalizeOrder());
  }

  // Safe restart — always stop first, then start after delay
  _safeRestart() {
    if (this._restartQueued) return;
    this._restartQueued = true;
    try { this.recognition.stop(); } catch(e) {}
    setTimeout(() => {
      this._restartQueued = false;
      if (this.isRecording && !this._processing && !this._isSpeaking) {
        try {
          this.recognition.start();
        } catch(e) {
          console.warn('Restart failed:', e);
          // Retry with longer delay
          setTimeout(() => {
            if (this.isRecording && !this._processing) {
              try { this.recognition.start(); } catch(e2) {}
            }
          }, 800);
        }
      }
    }, 350);
  }

  _resetSilenceTimer() {
    clearTimeout(this._silenceTimer);
    this._silenceTimer = setTimeout(() => {
      if (this.isRecording && this.finalTranscript.trim() && !this._processing) {
        const text = this.finalTranscript.trim();
        this.finalTranscript = '';
        // Stop recognition to prevent onresult during processing
        try { this.recognition.stop(); } catch(e) {}
        this.handleVoiceInput(text);
      }
    }, this._silenceTimeout);
  }

  toggleRecording() {
    if (this.isRecording) {
      // === STOP ===
      this.isRecording = false;
      this._processing = false;
      clearTimeout(this._silenceTimer);
      try { this.recognition.stop(); } catch(e) {}
      const text = this.finalTranscript.trim();
      this.finalTranscript = '';
      if (text) this.handleVoiceInput(text);
      this.updateUI();
    } else {
      // === START ===
      this._processing = false;
      this.finalTranscript = '';
      this.isRecording = true;
      this.updateUI();
      // Wait for any pending stop
      setTimeout(() => {
        if (this.isRecording) {
          try {
            this.recognition.start();
          } catch(e) {
            console.warn('Start failed:', e);
            setTimeout(() => {
              if (this.isRecording) {
                try { this.recognition.start(); } catch(e2) {
                  console.warn('Retry start failed:', e2);
                  this.isRecording = false;
                  this.updateUI();
                }
              }
            }, 800);
          }
        }
      }, 350);
    }
  }

  async handleVoiceInput(text) {
    if (this._processing) return; // prevent double-fire
    this._processing = true;

    // Add user message
    this.addMessage(text, 'user');
    this.setStatus('⏳ กำลังประมวลผล...', 'processing');

    // Add to history
    this.conversationHistory.push({ role: 'user', content: text });

    try {
      const response = await fetch('/api/voice/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          conversationHistory: this.conversationHistory.slice(-10)
        })
      });

      const data = await response.json();

      if (data.success) {
        const replyText = (data.reply || '').trim();
        this.addMessage(replyText, 'ai');
        this.conversationHistory.push({ role: 'model', content: replyText });

        // Handle action
        if (data.action === 'identify' && data.items && data.items.length > 0) {
          this.showConfirmationPopup(data.items);
        } else if (data.action === 'complete') {
          if (this.currentOrder.length > 0) {
            this.addMessage('👉 กดปุ่ม "🍳 ส่งไปครัว" ด้านล่างเพื่อยืนยันออเดอร์ครับ', 'ai');
            this.highlightSendButton();
          }
        }

        this._processing = false;

        // Fire TTS in background — don't block mic restart
        this.speak(replyText).then(() => {
          this._isSpeaking = false;
          if (this.isRecording) this._safeRestart();
        });

        // Restart mic immediately (don't wait for TTS)
        if (this.isRecording) {
          setTimeout(() => this._safeRestart(), 500);
        }
      } else {
        this.addMessage('ขออภัยครับ เกิดข้อผิดพลาด', 'ai');
        this._processing = false;
        if (this.isRecording) this._safeRestart();
      }
    } catch (err) {
      console.error('Error:', err);
      this.addMessage('ขออภัยครับ ไม่สามารถเชื่อมต่อได้', 'ai');
      this._processing = false;
      if (this.isRecording) this._safeRestart();
    }
    this.updateUI();
  }

  // ======== Confirmation Popup ========
  showConfirmationPopup(items) {
    this.pendingItems = items;

    const popupBody = document.getElementById('popupBody');
    let html = '';

    items.forEach((item) => {
      const itemName = item.nameTh || item.name || 'unknown';
      const itemNameEn = item.nameTh ? item.name : '';
      const qty = item.quantity || 1;
      const price = item.price || 0;
      const subtotal = price * qty;

      html += `
        <div class="popup-item">
          <div class="popup-item-name">${itemName}</div>
          ${itemNameEn ? `<div class="popup-item-name-en">${itemNameEn}</div>` : ''}
          <div class="popup-item-detail">
            <span class="popup-item-qty">×${qty}</span>
            <span class="popup-item-price">${subtotal} บาท</span>
          </div>
        </div>
      `;
    });

    if (items.length > 1) {
      const total = items.reduce((sum, item) => sum + ((item.price || 0) * (item.quantity || 1)), 0);
      html += `<div style="text-align:right;padding:8px 0;font-weight:700;font-size:16px;">รวม ${total} บาท</div>`;
    }

    popupBody.innerHTML = html;
    document.getElementById('popupOverlay').classList.add('show');
  }

  confirmAddToCart() {
    document.getElementById('popupOverlay').classList.remove('show');

    this.pendingItems.forEach(item => {
      const itemName = item.nameTh || item.name;
      const existing = this.currentOrder.find(o => o.name === itemName);
      if (existing) {
        existing.quantity += item.quantity || 1;
      } else {
        this.currentOrder.push({
          name: itemName,
          nameEn: item.name || '',
          quantity: item.quantity || 1,
          price: item.price || 0
        });
      }
    });

    this.pendingItems = [];
    this.refreshCartBar();
    this.showChatOrderSummary();
    this.speak('เพิ่มในตะกร้าเรียบร้อยครับ');
  }

  skipItems() {
    document.getElementById('popupOverlay').classList.remove('show');
    this.pendingItems = [];
    this.addMessage('👌 ไม่เป็นไรครับ พูดรายการใหม่ได้เลยครับ', 'ai');
    this.speak('ไม่เป็นไรครับ พูดรายการใหม่ได้เลย');
  }

  // ======== Cart Management ========
  refreshCartBar() {
    const cartBar = document.getElementById('cartBar');
    const cartCount = document.getElementById('cartCount');
    const cartTotal = document.getElementById('cartTotal');
    const sendBtn = document.getElementById('btnSendKitchen');

    const count = this.currentOrder.length;
    const total = this.currentOrder.reduce((sum, item) => sum + (item.price * item.quantity), 0);

    if (count > 0) {
      cartBar.classList.add('visible');
      cartCount.textContent = count;
      cartTotal.textContent = total.toLocaleString();
      sendBtn.disabled = false;
    } else {
      cartBar.classList.remove('visible');
      sendBtn.disabled = true;
    }
  }

  highlightSendButton() {
    const sendBtn = document.getElementById('btnSendKitchen');
    sendBtn.style.animation = 'pulse 0.8s 3';
    setTimeout(() => { sendBtn.style.animation = ''; }, 2400);
  }

  showChatOrderSummary() {
    if (this.currentOrder.length === 0) return;

    const chatArea = document.getElementById('chatArea');
    const existing = document.getElementById('orderSummary');
    if (existing) existing.remove();

    const summaryDiv = document.createElement('div');
    summaryDiv.className = 'order-summary';
    summaryDiv.id = 'orderSummary';

    let html = '<h3>🛒 ตะกร้าสินค้า</h3>';
    let total = 0;

    this.currentOrder.forEach((item, index) => {
      const subtotal = item.price * item.quantity;
      total += subtotal;
      html += `
        <div class="order-item">
          <span>
            ${item.name} ×${item.quantity}
            <button class="btn-remove-item" data-index="${index}" title="ลบรายการ">✕</button>
          </span>
          <span>${subtotal} บาท</span>
        </div>
      `;
    });

    html += `
      <div class="order-item order-total">
        <span>รวมทั้งหมด</span>
        <span>${total.toLocaleString()} บาท</span>
      </div>
    `;

    summaryDiv.innerHTML = html;
    chatArea.appendChild(summaryDiv);
    chatArea.scrollTop = chatArea.scrollHeight;

    summaryDiv.querySelectorAll('.btn-remove-item').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const idx = parseInt(e.target.dataset.index);
        this.removeFromCart(idx);
      });
    });
  }

  removeFromCart(index) {
    this.currentOrder.splice(index, 1);
    this.refreshCartBar();
    this.showChatOrderSummary();

    if (this.currentOrder.length === 0) {
      this.addMessage('🫙 ตะกร้าว่างแล้วครับ พูดสั่งเพิ่มได้เลย', 'ai');
      const s = document.getElementById('orderSummary');
      if (s) s.remove();
    }
  }

  // ======== Finalize Order (Send to Kitchen) ========
  async finalizeOrder() {
    if (this.currentOrder.length === 0) {
      this.addMessage('⚠️ ยังไม่มีรายการในตะกร้าครับ', 'ai');
      return;
    }

    const btn = document.getElementById('btnSendKitchen');
    btn.disabled = true;
    btn.textContent = '⏳ กำลังส่ง...';

    const total = this.currentOrder.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    const itemList = this.currentOrder.map(i => `${i.name} ×${i.quantity}`).join(', ');
    this.addMessage(`📋 ยืนยันออเดอร์: ${itemList}\nรวม ${total.toLocaleString()} บาท`, 'user');
    this.setStatus('⏳ กำลังส่งออเดอร์ไปครัว...', 'processing');

    try {
      const response = await fetch('/api/order/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items: this.currentOrder,
          tableId: 'T01'
        })
      });

      const data = await response.json();
      console.log('Order response:', data);

      if (data.success) {
        this.addMessage(`✅ ส่งออเดอร์ไปครัวแล้ว!\nรหัสออเดอร์: ${data.orderId}\nรวม: ${data.total.toLocaleString()} บาท\nขอบคุณที่ใช้บริการครับ 🎉`, 'ai');
        this.speak(`ส่งออเดอร์ไปครัวแล้วครับ รหัส ${data.orderId} รวม ${data.total} บาท`);

        this.currentOrder = [];
        this.conversationHistory = [];
        this.refreshCartBar();

        const s = document.getElementById('orderSummary');
        if (s) s.remove();

        // Sound effect
        try {
          const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
          const osc = audioCtx.createOscillator();
          const gain = audioCtx.createGain();
          osc.connect(gain);
          gain.connect(audioCtx.destination);
          osc.frequency.setValueAtTime(880, audioCtx.currentTime);
          osc.frequency.setValueAtTime(1100, audioCtx.currentTime + 0.1);
          gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
          osc.start();
          osc.stop(audioCtx.currentTime + 0.3);
        } catch(e) {}
      } else {
        this.addMessage(`❌ ส่งไม่สำเร็จ: ${data.error || 'ไม่ทราบสาเหตุ'}\nลองใหม่อีกครั้งครับ`, 'ai');
      }
    } catch (err) {
      console.error('Order error:', err);
      this.addMessage(`❌ เชื่อมต่อ POS ไม่ได้: ${err.message}\nลองใหม่อีกครั้งครับ`, 'ai');
    }

    btn.textContent = '🍳 ส่งไปครัว';
    btn.disabled = this.currentOrder.length === 0;
    this.setStatus('🎤 กดไมค์เพื่อพูด', '');
  }

  // ======== UI Helpers ========
  addMessage(text, sender) {
    const chatArea = document.getElementById('chatArea');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    const avatar = sender === 'ai' ? '🤖' : '👤';
    const displayText = text.replace(/\n/g, '<br>');

    messageDiv.innerHTML = `
      <div class="message-avatar">${avatar}</div>
      <div class="message-bubble">${displayText}</div>
    `;

    chatArea.appendChild(messageDiv);
    chatArea.scrollTop = chatArea.scrollHeight;
  }

  async speak(text) {
    if (!text || !text.trim()) return;
    this._isSpeaking = true;
    try {
      const resp = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      const data = await resp.json();
      if (data.success && data.audio) {
        const audio = new Audio('data:audio/mp3;base64,' + data.audio);
        await audio.play().catch(e => console.warn('Audio play failed:', e));
      } else {
        this._speakBrowser(text);
      }
    } catch (e) {
      console.warn('Backend TTS failed, using browser fallback:', e);
      this._speakBrowser(text);
    }
    this._isSpeaking = false;
  }

  _speakBrowser(text) {
    const cleanText = text.replace(/[^\u0e00-\u0e7fa-zA-Z0-9 \t.,!?-]/g, ' ').replace(/\s+/g, ' ').trim();
    if (!cleanText) return;
    if (this.synthesis.speaking) this.synthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = 'th-TH';
    utterance.rate = 1.0;

    const voices = this.synthesis.getVoices();
    const thaiVoice = voices.find(v => v.lang.startsWith('th'));
    if (thaiVoice) utterance.voice = thaiVoice;

    utterance.onerror = (e) => console.warn('TTS error:', e.error);

    try { this.synthesis.speak(utterance); } catch (e) {}
  }

  clearChat() {
    this.currentOrder = [];
    this.conversationHistory = [];
    this.finalTranscript = '';
    this.pendingItems = [];
    this._processing = false;

    document.getElementById('popupOverlay').classList.remove('show');
    this.refreshCartBar();

    const chatArea = document.getElementById('chatArea');
    chatArea.innerHTML = `
      <div class="message ai">
        <div class="message-avatar">🤖</div>
        <div class="message-bubble">
          สวัสดีครับ! ยินดีต้อนรับสู่ร้านอาหารไทย 🍜<br>
          กดไมค์แล้วพูดชื่อเมนูที่ต้องการได้เลยครับ
        </div>
      </div>
    `;
  }

  updateUI() {
    const micBtn = document.getElementById('micBtn');
    const status = document.getElementById('status');

    if (this.isRecording) {
      micBtn.classList.add('recording');
      micBtn.textContent = '🔴 กดเพื่อหยุด';
      status.textContent = '🎤 กำลังฟัง...';
      status.className = 'status listening';
    } else {
      micBtn.classList.remove('recording');
      micBtn.textContent = '🎤 กดเพื่อพูด';
      status.textContent = 'พร้อมรับคำสั่ง';
      status.className = 'status';
    }
  }

  setStatus(text, className) {
    const status = document.getElementById('status');
    status.textContent = text;
    status.className = `status ${className}`;
  }
}

// Initialize when page loads
window.addEventListener('load', () => {
  window.speechSynthesis.getVoices();
  window.speechSynthesis.onvoiceschanged = () => {
    window.speechSynthesis.getVoices();
  };

  new VoicePOS();

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js', { scope: '/voice/' })
      .then(reg => console.log('[PWA] SW registered:', reg.scope))
      .catch(err => console.warn('[PWA] SW registration failed:', err));
  }
});
