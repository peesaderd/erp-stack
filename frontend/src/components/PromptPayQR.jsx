import { useState, useEffect } from 'react';

const PromptPayQR = ({ qrData, amount, expiresAt, onExpired }) => {
  const [timeLeft, setTimeLeft] = useState('');

  useEffect(() => {
    const timer = setInterval(() => {
      const now = Date.now();
      const exp = new Date(expiresAt).getTime();
      const diff = exp - now;

      if (diff <= 0) {
        clearInterval(timer);
        setTimeLeft('หมดอายุ');
        onExpired?.();
        return;
      }

      const minutes = Math.floor(diff / 60000);
      const seconds = Math.floor((diff % 60000) / 1000);
      setTimeLeft(`${minutes}:${seconds.toString().padStart(2, '0')}`);
    }, 1000);

    return () => clearInterval(timer);
  }, [expiresAt, onExpired]);

  return (
    <div className="promptpay-qr-container">
      <div className="qr-header">
        <h3>สแกนเพื่อชำระเงิน</h3>
        <p className="qr-amount">฿{amount.toFixed(2)}</p>
      </div>
      
      <div className="qr-display">
        <img src={qrData} alt="PromptPay QR Code" className="qr-image" />
      </div>

      <div className="qr-timer">
        <span className="timer-label">หมดอายุใน</span>
        <span className="timer-value">{timeLeft}</span>
      </div>

      <div className="qr-instructions">
        <p>1. เปิดแอปธนาคารบนมือถือของคุณ</p>
        <p>2. เลือกสแกน QR Code</p>
        <p>3. ตรวจสอบยอดเงินและกดยืนยัน</p>
      </div>
    </div>
  );
};

export default PromptPayQR;
