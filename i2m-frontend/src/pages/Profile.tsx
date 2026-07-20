import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

export default function Profile() {
  const navigate = useNavigate()
  const [darkMode, setDarkMode] = useState(() => document.documentElement.classList.contains('dark'))
  const [shopName, setShopName] = useState(localStorage.getItem('i2m_shop_name') || '')
  const [target, setTarget] = useState(localStorage.getItem('i2m_target') || '')

  const [saved, setSaved] = useState(false)

  // Initialize dark mode from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('i2m_dark_mode') === 'true'
    document.documentElement.classList.toggle('dark', saved)
  }, [])

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

  const currentTab = window.location.pathname === '/' ? 'studio' : window.location.pathname === '/gallery' ? 'gallery' : 'profile'

  return (
    <>
      {/* Mobile Header - Aether style */}
      <header className="md:hidden bg-surface/70 backdrop-blur-xl fixed top-0 w-full z-50 border-b border-outline-variant/10 shadow-sm shadow-secondary/5 flex justify-between items-center px-margin-mobile h-16">
        <button className="text-primary active:scale-95 duration-200 hover:bg-surface-variant/50 transition-colors p-2 rounded-full flex items-center justify-center">
          <span className="material-symbols-outlined">menu</span>
        </button>
        <h1 className="font-display text-display-lg-mobile tracking-tighter text-primary">I2M STUDIO</h1>
        <div className="w-8 h-8 rounded-full overflow-hidden bg-gradient-to-br from-secondary/30 to-secondary/10 border border-secondary/20 flex items-center justify-center">
          <span className="material-symbols-outlined text-[18px] text-secondary">person</span>
        </div>
      </header>

      <div className="min-h-screen bg-background pb-28 md:pb-0 md:pl-72 pt-16 md:pt-0">
        <div className="max-w-container-max mx-auto p-margin-mobile md:p-margin-desktop">
          {/* Page Header */}
          <header className="mb-6">
            <h1 className="font-display text-display-sm md:text-display-md text-primary tracking-tight">Profile</h1>
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
                <div key={stat.label} className="text-center p-3 rounded-xl bg-surface-container-low glass-panel">
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
                  className="w-full px-4 py-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-body-md text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:ring-2 focus:ring-secondary/40 transition-all glass-panel"
                />
              </div>
              <div>
                <label className="text-label-sm text-on-surface-variant mb-1.5 block">กลุ่มเป้าหมาย</label>
                <input
                  type="text"
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                  placeholder="เช่น สายดูแลผิว วัยทำงาน 25-40"
                  className="w-full px-4 py-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-body-md text-on-surface placeholder:text-on-surface-variant/60 focus:outline-none focus:ring-2 focus:ring-secondary/40 transition-all glass-panel"
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
                <div className={`absolute top-1 left-1 w-6 h-6 rounded-full bg-white shadow-md transition-transform duration-300 flex items-center justify-center glass-panel ${
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
  
        {/* Links */}
        <div className="p-5 rounded-2xl glass-panel shadow-glass border border-outline-variant/10 mb-4">
          <h3 className="text-label-md text-on-surface uppercase tracking-widest mb-4">เครื่องมือ</h3>
          <div className="flex flex-col gap-2">
            <button onClick={() => navigate('/payment')} className="flex items-center gap-3 px-4 py-3 rounded-xl bg-surface-container-low hover:bg-surface-container transition-all text-body-md text-on-surface">
              <span className="material-symbols-outlined text-secondary" style={{ fontVariationSettings: "'FILL' 1" }}>qr_code_scanner</span>
              <span>สร้าง QR PromptPay</span>
              <span className="material-symbols-outlined text-on-surface-variant ml-auto">chevron_right</span>
            </button>
            <button onClick={() => navigate('/scrape')} className="flex items-center gap-3 px-4 py-3 rounded-xl bg-surface-container-low hover:bg-surface-container transition-all text-body-md text-on-surface">
              <span className="material-symbols-outlined text-secondary" style={{ fontVariationSettings: "'FILL' 1" }}>travel_explore</span>
              <span>ค้นหาสินค้าจาก URL</span>
              <span className="material-symbols-outlined text-on-surface-variant ml-auto">chevron_right</span>
            </button>
          </div>
        </div>

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

      {/* Desktop Sidebar - Aether style */}
      <nav className="hidden md:flex flex-col h-full w-72 rounded-r-2xl bg-surface dark:bg-surface-container divide-y divide-outline-variant/10 shadow-xl fixed left-0 top-0 bottom-0 z-40 p-md transition-all duration-200">
        <div className="flex items-center gap-sm pb-md">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-secondary to-[#2c248b] flex items-center justify-center text-on-secondary">
            <span className="material-symbols-outlined text-[28px]" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
          </div>
          <div>
            <h2 className="text-headline-sm text-primary">I2M Studio</h2>
            <p className="text-label-sm text-on-surface-variant">Content Creator</p>
          </div>
        </div>
        <div className="flex-1 py-md space-y-2">
          <button
            onClick={() => navigate('/')}
            className={`w-full flex items-center gap-sm px-4 py-3 rounded-xl transition-all duration-200 ${
              currentTab === 'studio'
                ? 'bg-secondary/10 text-secondary font-bold'
                : 'text-on-surface-variant hover:bg-surface-variant hover:text-on-surface'
            }`}
          >
            <span className="material-symbols-outlined" style={{ fontVariationSettings: currentTab === 'studio' ? "'FILL' 1" : "'FILL' 0" }}>auto_awesome</span>
            <span>Directives</span>
          </button>
          <button
            onClick={() => navigate('/gallery')}
            className={`w-full flex items-center gap-sm px-4 py-3 rounded-xl transition-all duration-200 ${
              currentTab === 'gallery'
                ? 'bg-secondary/10 text-secondary font-bold'
                : 'text-on-surface-variant hover:bg-surface-variant hover:text-on-surface'
            }`}
          >
            <span className="material-symbols-outlined" style={{ fontVariationSettings: currentTab === 'gallery' ? "'FILL' 1" : "'FILL' 0" }}>layers</span>
            <span>Models</span>
          </button>
          <button
            onClick={() => navigate('/profile')}
            className={`w-full flex items-center gap-sm px-4 py-3 rounded-xl transition-all duration-200 ${
              currentTab === 'profile'
                ? 'bg-secondary/10 text-secondary font-bold'
                : 'text-on-surface-variant hover:bg-surface-variant hover:text-on-surface'
            }`}
          >
            <span className="material-symbols-outlined" style={{ fontVariationSettings: currentTab === 'profile' ? "'FILL' 1" : "'FILL' 0" }}>settings</span>
            <span>Settings</span>
          </button>
        </div>
        <div className="pt-md text-label-sm text-on-surface-variant/60 text-center">
          <p>Pro Plan Active</p>
          <p className="text-secondary mt-1">1,200 Credits</p>
        </div>
      </nav>
    </>
  )
}
