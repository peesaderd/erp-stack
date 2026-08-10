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
    
    this.init();
  }

  init() {
    // Check browser support
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('เบราว์เซอร์นี้ไม่รองรับ Voice Recognition\nกรุณาใช้ Chrome หรือ Edge');
      return;
    }

    // Setup Speech Recognition
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.recognition = new SpeechRecognition();
    this.recognition.lang = 'th-TH';
    this.recognition.continuous = true;
    this.recognition.interimResults = true;

    // Event handlers
    this.recognition.onstart = () => {
      this.isRecording = true;
      this.updateUI();
    };

    this.recognition.onresult = (event) => {
      const lastResult = event.results[event.results.length - 1];
      const transcript = lastResult[0].transcript;
      if (lastResult.isFinal) {
        this.finalTranscript += transcript + ' ';
        this._resetSilenceTimer();
      } else {
        this.setStatus('🎤 ' + transcript, 'listening');
      }
    };

    this.recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      if (event.error === 'no-speech') {
        if (this.isRecording) this._autoRestart();
        return;
      }
      this.setStatus('เกิดข้อผิดพลาด กรุณาลองใหม่', 'error');
      this.isRecording = false;
      this.updateUI();
    };

    this.recognition.onend = () => {
      if (this.isRecording && !this._isSpeaking) {
        const text = this.finalTranscript.trim();
        this.finalTranscript = '';
        if (text) {
          this.handleVoiceInput(text);
        } else {
          this._autoRestart();
        }
      } else {
        this.updateUI();
      }
    };

    // Button handlers
    document.getElementById('micBtn').addEventListener('click', () => this.toggleRecording());
    document.getElementById('clearBtn').addEventListener('click', () => this.clearChat());
    document.getElementById('btnAddCart').addEventListener('click', () => this.confirmAddToCart());
    document.getElementById('btnSkip').addEventListener('click', () => this.skipItems());
    document.getElementById('btnSendKitchen').addEventListener('click', () => this.finalizeOrder());
  }

  _resetSilenceTimer() {
    clearTimeout(this._silenceTimer);
    this._silenceTimer = setTimeout(() => {
      if (this.isRecording && this.finalTranscript.trim()) {
        const text = this.finalTranscript.trim();
        this.finalTranscript = '';
        this.recognition.stop();
        this.handleVoiceInput(text);
      }
    }, this._silenceTimeout);
  }

  _autoRestart() {
    setTimeout(() => {
      if (this.isRecording && !this._isSpeaking) {
        try { this.recognition.start(); } catch(e) { console.warn('Restart failed:', e); }
      }
    }, 300);
  }

  toggleRecording() {
    if (this.isRecording) {
      this.isRecording = false;
      clearTimeout(this._silenceTimer);
      this.recognition.stop();
      const text = this.finalTranscript.trim();
      if (text) this.handleVoiceInput(text);
      this.finalTranscript = '';
      this.updateUI();
    } else {
      this.isRecording = true;
      this.finalTranscript = '';
      this.recognition.start();
      this.updateUI();
    }
  }

  async handleVoiceInput(text) {
    // Add user message
    this.addMessage(text, 'user');
    this.setStatus('⏳ กำลังประมวลผล...', 'processing');

    // Add to history
    this.conversationHistory.push({ role: 'user', content: text });

    try {
      // Send to backend
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
          // Found items → show confirmation popup
          this.showConfirmationPopup(data.items);
        } else if (data.action === 'complete') {
          // User wants to finalize → ask for final confirmation
          // The cart bar "Send to Kitchen" button is always visible
          if (this.currentOrder.length > 0) {
            this.addMessage('👉 กดปุ่ม "🍳 ส่งไปครัว" ด้านล่างเพื่อยืนยันออเดอร์ครับ', 'ai');
            this.highlightSendButton();
          }
        }
        // 'question' → nothing special, just reply shown

        // Speak reply via Edge TTS
        await this.speak(replyText);
        // Auto-restart listening after TTS
        if (this.isRecording) this._autoRestart();
      } else {
        this.addMessage('ขออภัยครับ เกิดข้อผิดพลาด', 'ai');
      }
    } catch (err) {
      console.error('Error:', err);
      this.addMessage('ขออภัยครับ ไม่สามารถเชื่อมต่อได้', 'ai');
    }
    this.updateUI();
  }

  // ======== Confirmation Popup ========
  showConfirmationPopup(items) {
    this.pendingItems = items;

    const popupBody = document.getElementById('popupBody');
    let html = '';

    items.forEach((item, index) => {
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

    // Show total if multiple items
    if (items.length > 1) {
      const total = items.reduce((sum, item) => sum + ((item.price || 0) * (item.quantity || 1)), 0);
      html += `<div style="text-align:right;padding:8px 0;font-weight:700;font-size:16px;">รวม ${total} บาท</div>`;
    }

    popupBody.innerHTML = html;

    // Show popup
    document.getElementById('popupOverlay').classList.add('show');
  }

  confirmAddToCart() {
    // Hide popup
    document.getElementById('popupOverlay').classList.remove('show');

    // Add pending items to cart
    this.pendingItems.forEach(item => {
      const itemName = item.nameTh || item.name;
      const existing = this.currentOrder.find(o => o.name === itemName);
      if (existing) {
        existing.quantity += item.quantity || 1;
      } else {
        this.currentOrder.push({
          name: itemName,
          quantity: item.quantity || 1,
          price: item.price || 0
        });
      }
    });

    this.pendingItems = [];
    this.refreshCartBar();
    this.showChatOrderSummary();
    this.addMessage('✅ เพิ่มในตะกร้าเรียบร้อยครับ พูดต่อหรือกดส่งไปครัวได้เลย', 'ai');
    this.speak('เพิ่มในตะกร้าเรียบร้อยครับ');
  }

  skipItems() {
    // Hide popup
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

    // Remove existing summary if any
    const existing = document.querySelector('.order-summary');
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

    // Add remove handlers
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
      // Remove summary
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

    // Show total in chat
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
          customerName: 'Voice Customer',
          tableId: 'VOICE'
        })
      });

      const data = await response.json();

      if (data.success) {
        this.addMessage(`✅ ส่งออเดอร์ไปครัวแล้ว!\nรหัสออเดอร์: ${data.orderId}\nรวม: ${data.total.toLocaleString()} บาท\nขอบคุณที่ใช้บริการครับ 🎉`, 'ai');
        this.speak(`ส่งออเดอร์ไปครัวแล้วครับ รหัส ${data.orderId} รวม ${data.total} บาท`);

        // Reset cart
        this.currentOrder = [];
        this.conversationHistory = [];
        this.refreshCartBar();
        
        // Remove summary
        const s = document.getElementById('orderSummary');
        if (s) s.remove();

        // Sound effect feedback
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
        } catch(e) { /* ignore audio ctx errors */ }
      } else {
        throw new Error(data.error || 'Order creation failed');
      }
    } catch (err) {
      console.error('Order error:', err);
      this.addMessage('ขออภัยครับ ไม่สามารถส่งออเดอร์ได้ กรุณาลองใหม่', 'ai');
    }

    btn.textContent = '🍳 ส่งไปครัว';
    this.setStatus('🎤 กดไมค์เพื่อพูด', '');
  }

  // ======== UI Helpers ========
  addMessage(text, sender) {
    const chatArea = document.getElementById('chatArea');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    const avatar = sender === 'ai' ? '🤖' : '👤';
    
    // Convert newlines to <br>
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

  _toThai(n) {
    const D = ['ศูนย์','หนึ่ง','สอง','สาม','สี่','ห้า','หก','เจ็ด','แปด','เก้า'];
    if (n === 0) return D[0];
    if (n < 10) return D[n];
    if (n < 20) return 'สิบ' + (n === 10 ? '' : D[n-10]);
    if (n < 100) { const t = Math.floor(n/10), o = n%10; return D[t] + 'สิบ' + (o ? D[o] : ''); }
    if (n < 1000) { const h = Math.floor(n/100), r = n%100; return D[h] + 'ร้อย' + (r < 10 ? (r ? D[r] : '') : this._toThai(r)); }
    return String(n);
  }

  _speakBrowser(text) {
    // Normalize numbers for Thai TTS
    let cleanText = text.replace(/(\d{1,2}):(\d{2})/g, (m, h, min) => {
      const H = parseInt(h), M = parseInt(min);
      if (H < 6) return 'ตี' + (H === 0 ? 'สิบสอง' : this._toThai(H));
      if (H < 12) return this._toThai(H) + 'โมง' + (M === 0 ? '' : M + 'นาที');
      if (H < 13) return 'สิบสองโมง' + (M === 0 ? '' : M + 'นาที');
      if (H < 18) return 'บ่าย' + this._toThai(H-12) + 'โมง' + (M === 0 ? '' : M + 'นาที');
      return this._toThai(H-17) + 'ทุ่ม' + (M === 0 ? '' : this._toThai(M) + 'นาที');
    });
    cleanText = cleanText.replace(/(\d{1,3})(?![:\d])/g, (m, num) => {
      const n = parseInt(num);
      return n <= 999 ? this._toThai(n) : m;
    });
    cleanText = cleanText.replace(/[^\u0e00-\u0e7fa-zA-Z0-9 \t.,!?-]/g, ' ').replace(/\s+/g, ' ').trim();
    if (!cleanText) return;
    if (this.synthesis.speaking) this.synthesis.cancel();
    }

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = 'th-TH';
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    // Try to find Thai voice
    const voices = this.synthesis.getVoices();
    const thaiVoice = voices.find(v => v.lang.startsWith('th'));
    if (thaiVoice) {
      utterance.voice = thaiVoice;
    }

    // Error handling
    utterance.onerror = (e) => {
      console.warn('TTS error:', e.error);
    };

    // On mobile Chrome, speech synthesis needs user gesture or resumes on interaction
    try {
      this.synthesis.speak(utterance);
    } catch (e) {
      console.warn('TTS failed:', e.message);
    }
  }

  clearChat() {
    // Reset everything
    this.currentOrder = [];
    this.conversationHistory = [];
    this.finalTranscript = '';
    this.pendingItems = [];
    
    // Hide popup if open
    document.getElementById('popupOverlay').classList.remove('show');
    
    // Refresh cart bar
    this.refreshCartBar();

    // Reset chat area
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
  // Load voices first
  window.speechSynthesis.getVoices();
  window.speechSynthesis.onvoiceschanged = () => {
    window.speechSynthesis.getVoices();
  };

  // Start Voice POS
  new VoicePOS();

  // Register Service Worker for PWA
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js', { scope: '/voice/' })
      .then(reg => console.log('[PWA] SW registered:', reg.scope))
      .catch(err => console.warn('[PWA] SW registration failed:', err));
  }
});
