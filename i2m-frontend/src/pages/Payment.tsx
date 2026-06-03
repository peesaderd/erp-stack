import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function Payment() {
  const navigate = useNavigate()
  const [amount, setAmount] = useState('')
  const [phone, setPhone] = useState('0812345678')
  const [reference, setReference] = useState('')
  const [qrData, setQrData] = useState<{qr_base64: string; qr_payload: string; amount: number} | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleGenerate = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/i2m/etsy-img/payment/create-qr', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount: parseFloat(amount) || 0,
          phone: phone || '0812345678',
          name: localStorage.getItem('i2m_shop_name') || 'I2M Studio',
          reference: reference || '',
        }),
      })
      const data = await res.json()
      if (data.ok) {
        setQrData(data)
      } else {
        setError('Failed to generate QR')
      }
    } catch (e: any) {
      setError(e.message || 'Error')
    } finally {
      setLoading(false)
    }
  }

  const handleClear = () => {
    setQrData(null)
    setAmount('')
    setReference('')
  }

  return (
    <div className="min-h-screen bg-background pb-28 md:pb-0 md:pl-72">
      <div className="max-w-container-max mx-auto p-margin-mobile md:p-margin-desktop pt-16 md:pt-0">
        {/* Header */}
        <header className="md:hidden bg-surface/70 backdrop-blur-xl fixed top-0 w-full z-50 border-b border-outline-variant/10 shadow-sm shadow-secondary/5 flex justify-between items-center px-margin-mobile h-16">
          <button onClick={() => navigate('/profile')}>
            <span className="material-symbols-outlined text-on-surface-variant">arrow_back</span>
          </button>
          <h1 className="font-display text-display-lg-mobile tracking-tighter">ชำระเงิน</h1>
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-secondary to-[#2c248b] flex items-center justify-center text-on-secondary cursor-pointer">
            <span className="material-symbols-outlined text-[16px]">person</span>
          </div>
        </header>

        <div className="flex flex-col items-center">
          <h1 className="text-headline-md text-primary tracking-tight mb-6 hidden md:block">ชำระเงิน</h1>

          {!qrData ? (
            <div className="w-full max-w-md p-5 rounded-2xl glass-panel shadow-glass border border-outline-variant/10">
              <h3 className="text-label-md text-on-surface uppercase tracking-widest mb-4">รายละเอียดการชำระ</h3>
              
              <div className="flex flex-col gap-4">
                <div>
                  <label className="text-label-sm text-on-surface-variant mb-1.5 block">จำนวนเงิน (บาท)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="199.00"
                    className="w-full px-4 py-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-body-md text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:ring-2 focus:ring-secondary/40"
                  />
                </div>
                <div>
                  <label className="text-label-sm text-on-surface-variant mb-1.5 block">เบอร์ PromptPay</label>
                  <input
                    type="text"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="0812345678"
                    className="w-full px-4 py-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-body-md text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:ring-2 focus:ring-secondary/40"
                  />
                </div>
                <div>
                  <label className="text-label-sm text-on-surface-variant mb-1.5 block">ออเดอร์ / อ้างอิง</label>
                  <input
                    type="text"
                    value={reference}
                    onChange={(e) => setReference(e.target.value)}
                    placeholder="เช่น FYNE-BHA-001"
                    className="w-full px-4 py-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-body-md text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:ring-2 focus:ring-secondary/40"
                  />
                </div>
                <button
                  onClick={handleGenerate}
                  disabled={loading || !amount}
                  className="w-full py-3 rounded-xl bg-secondary text-on-secondary text-label-md flex items-center justify-center gap-2 shadow-glass-lg hover:shadow-[0_8px_32px_rgba(79,70,229,0.3)] transition-all btn-press disabled:opacity-40"
                >
                  {loading ? (
                    <span className="material-symbols-outlined animate-spin text-[18px]">progress_activity</span>
                  ) : (
                    <><span className="material-symbols-outlined text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>qr_code_scanner</span> สร้าง QR PromptPay</>
                  )}
                </button>
                {error && <p className="text-label-sm text-error text-center">{error}</p>}
              </div>
            </div>
          ) : (
            <div className="w-full max-w-sm p-5 rounded-2xl glass-panel shadow-glass border border-outline-variant/10 text-center">
              <h3 className="text-label-md text-on-surface uppercase tracking-widest mb-3">สแกนเพื่อชำระ</h3>
              
              <div className="bg-white p-4 rounded-xl mb-4 inline-block shadow-sm">
                <img
                  src={`data:image/png;base64,${qrData.qr_base64}`}
                  alt="PromptPay QR"
                  className="w-60 h-60"
                />
              </div>
              
              <div className="flex flex-col gap-1 mb-4">
                <p className="text-display-sm text-primary font-semibold">{qrData.amount.toFixed(2)} ฿</p>
                <p className="text-body-sm text-on-surface-variant">สแกนด้วยแอปธนาคาร</p>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={handleClear}
                  className="flex-1 py-2 rounded-xl border border-outline-variant/30 text-label-sm hover:bg-surface-variant transition-all"
                >
                  <span className="material-symbols-outlined text-[16px]">refresh</span> ใหม่
                </button>
                <button
                  onClick={() => {
                    const a = document.createElement('a')
                    a.href = `data:image/png;base64,${qrData.qr_base64}`
                    a.download = `payment-${qrData.amount}-${Date.now()}.png`
                    a.click()
                  }}
                  className="flex-1 py-2 rounded-xl bg-secondary text-on-secondary text-label-sm flex items-center justify-center gap-1 btn-press"
                >
                  <span className="material-symbols-outlined text-[16px]">download</span> ดาวน์โหลด
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Mobile Bottom Tab Bar */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-surface/80 backdrop-blur-2xl border-t border-outline-variant/10 shadow-nav rounded-t-2xl">
        <div className="flex justify-around items-center h-20 px-2">
          {[
            { path: '/', icon: 'auto_awesome', label: 'Studio' },
            { path: '/gallery', icon: 'grid_view', label: 'Gallery' },
            { path: '/profile', icon: 'person', label: 'Profile' },
          ].map(tab => (
            <button
              key={tab.path}
              onClick={() => navigate(tab.path)}
              className="flex flex-col items-center justify-center gap-0.5 px-4 py-2 rounded-2xl transition-all duration-300 btn-press text-on-surface-variant hover:text-secondary"
            >
              <span className="material-symbols-outlined text-[24px]">{tab.icon}</span>
              <span className="text-label-sm">{tab.label}</span>
            </button>
          ))}
        </div>
      </nav>
    </div>
  )
}
