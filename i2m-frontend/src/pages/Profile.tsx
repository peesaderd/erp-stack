import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function Profile() {
  const navigate = useNavigate()
  const [darkMode, setDarkMode] = useState(() => document.documentElement.classList.contains('dark'))
  const [shopName, setShopName] = useState(localStorage.getItem('i2m_shop_name') || '')
  const [target, setTarget] = useState(localStorage.getItem('i2m_target') || '')

  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    localStorage.setItem('i2m_shop_name', shopName)
    localStorage.setItem('i2m_target', target)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const toggleDarkMode = () => {
    const next = !darkMode
    setDarkMode(next)
    document.documentElement.classList.toggle('dark', next)
    localStorage.setItem('i2m_dark_mode', String(next))
  }

  const generationCount = (() => {
    try {
      const items = JSON.parse(localStorage.getItem('i2m_generations') || '[]')
      const images = items.filter((i: any) => i.type === 'image').length
      const videos = items.filter((i: any) => i.type === 'video').length
      return { total: items.length, images, videos }
    } catch { return { total: 0, images: 0, videos: 0 } }
  })()

  return (
    <div className="min-h-screen bg-background pb-28 md:pb-0 md:pl-72">
      <div className="max-w-container-max mx-auto p-margin-mobile md:p-margin-desktop">
        {/* Page Header */}
        <header className="mb-6">
          <h1 className="text-display-sm md:text-display-md text-primary tracking-tight">Profile</h1>
          <p className="text-body-lg text-on-surface-variant mt-1">ตั้งค่าและสถิติ</p>
        </header>

        {/* Stats Card */}
        <div className="p-5 rounded-2xl glass-panel shadow-glass border border-outline-variant/10 mb-4">
          <h3 className="text-label-md text-on-surface uppercase tracking-widest mb-4">สถิติ</h3>
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'ทั้งหมด', value: generationCount.total },
              { label: 'รูป', value: generationCount.images },
              { label: 'วิดีโอ', value: generationCount.videos },
            ].map(stat => (
              <div key={stat.label} className="text-center p-3 rounded-xl bg-surface-container-low">
                <p className="text-display-sm text-primary font-semibold">{stat.value}</p>
                <p className="text-label-sm text-on-surface-variant mt-1">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Settings Card */}
        <div className="p-5 rounded-2xl glass-panel shadow-glass border border-outline-variant/10 mb-4">
          <h3 className="text-label-md text-on-surface uppercase tracking-widest mb-4">ตั้งค่าร้านค้า</h3>
          <div className="flex flex-col gap-4">
            <div>
              <label className="text-label-sm text-on-surface-variant mb-1.5 block">ชื่อร้าน / แบรนด์</label>
              <input
                type="text"
                value={shopName}
                onChange={(e) => setShopName(e.target.value)}
                placeholder="ชื่อร้านค้าของคุณ"
                className="w-full px-4 py-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-body-md text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:ring-2 focus:ring-secondary/40 transition-all"
              />
            </div>
            <div>
              <label className="text-label-sm text-on-surface-variant mb-1.5 block">กลุ่มเป้าหมาย</label>
              <input
                type="text"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                placeholder="เช่น สายดูแลผิว วัยทำงาน 25-40"
                className="w-full px-4 py-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-body-md text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:ring-2 focus:ring-secondary/40 transition-all"
              />
            </div>
            <button
              onClick={handleSave}
              className="self-start px-6 py-3 rounded-xl bg-secondary text-on-secondary text-body-md flex items-center gap-2 shadow-glass-lg hover:shadow-[0_8px_32px_rgba(79,70,229,0.3)] transition-all duration-200 btn-press"
            >
              <span className="material-symbols-outlined text-[18px]">{saved ? 'check' : 'save'}</span>
              {saved ? 'บันทึกแล้ว!' : 'บันทึก'}
            </button>
          </div>
        </div>

        {/* Display Card */}
        <div className="p-5 rounded-2xl glass-panel shadow-glass border border-outline-variant/10 mb-4">
          <h3 className="text-label-md text-on-surface uppercase tracking-widest mb-4">การแสดงผล</h3>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-body-md text-on-surface">Dark Mode</p>
              <p className="text-body-sm text-on-surface-variant">{darkMode ? 'เปิด' : 'ปิด'}</p>
            </div>
            <button
              onClick={toggleDarkMode}
              className={`relative w-14 h-8 rounded-full transition-colors duration-300 ${
                darkMode ? 'bg-secondary' : 'bg-outline-variant'
              }`}
            >
              <div className={`absolute top-1 left-1 w-6 h-6 rounded-full bg-white shadow-md transition-transform duration-300 flex items-center justify-center ${
                darkMode ? 'translate-x-6' : ''
              }`}>
                <span className="material-symbols-outlined text-[14px]" style={{ fontVariationSettings: "'FILL' 1" }}>
                  {darkMode ? 'dark_mode' : 'light_mode'}
                </span>
              </div>
            </button>
          </div>
        </div>

        {/* About */}
        <div className="p-5 rounded-2xl glass-panel shadow-glass border border-outline-variant/10">
          <h3 className="text-label-md text-on-surface uppercase tracking-widest mb-2">เกี่ยวกับ</h3>
          <p className="text-body-sm text-on-surface-variant">I2M Studio — Image to Material</p>
          <p className="text-body-sm text-on-surface-variant/60 mt-1">v1.0 • Made with Aether Design System</p>
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
              className={`flex flex-col items-center justify-center gap-0.5 px-4 py-2 rounded-2xl transition-all duration-300 btn-press ${
                tab.path === '/profile' ? 'text-secondary bg-secondary-container/20' : 'text-on-surface-variant hover:text-secondary'
              }`}
            >
              <span className="material-symbols-outlined text-[24px]" style={{ fontVariationSettings: tab.path === '/profile' ? "'FILL' 1" : "'FILL' 0" }}>{tab.icon}</span>
              <span className="text-label-sm">{tab.label}</span>
            </button>
          ))}
        </div>
      </nav>
    </div>
  )
}
