import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function ProductScrape() {
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleScrape = async () => {
    if (!url.trim()) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await fetch('/api/i2m/etsy-img/product/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim() }),
      })
      const data = await res.json()
      if (data.ok) {
        setResult(data)
      } else {
        setError(data.error || 'Scrape failed')
      }
    } catch (e: any) {
      setError(e.message || 'Error')
    } finally {
      setLoading(false)
    }
  }

  const handleSendToStudio = () => {
    if (result?.title) {
      localStorage.setItem('i2m_scrape_product', JSON.stringify(result))
      navigate('/')
    }
  }

  return (
    <div className="min-h-screen bg-background pb-28 md:pb-0 md:pl-72">
      <div className="max-w-container-max mx-auto p-margin-mobile md:p-margin-desktop pt-16 md:pt-0">
        {/* Mobile Header */}
        <header className="md:hidden bg-surface/70 backdrop-blur-xl fixed top-0 w-full z-50 border-b border-outline-variant/10 shadow-sm shadow-secondary/5 flex justify-between items-center px-margin-mobile h-16">
          <button onClick={() => navigate('/')}>
            <span className="material-symbols-outlined text-on-surface-variant">arrow_back</span>
          </button>
          <h1 className="font-display text-display-lg-mobile tracking-tighter">ค้นหาสินค้า</h1>
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-secondary to-[#2c248b] flex items-center justify-center text-on-secondary">
            <span className="material-symbols-outlined text-[16px]">person</span>
          </div>
        </header>

        <h1 className="text-headline-md text-primary tracking-tight mb-6 hidden md:block">ค้นหาสินค้า</h1>

        {/* URL Input */}
        <div className="max-w-2xl mx-auto p-5 rounded-2xl glass-panel shadow-glass border border-outline-variant/10 mb-4">
          <h3 className="text-label-md text-on-surface uppercase tracking-widest mb-4">URL สินค้า</h3>
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://shopee.co.th/... หรือ https://www.fyneskin.com/..."
              className="flex-1 px-4 py-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-body-md text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:ring-2 focus:ring-secondary/40"
              onKeyDown={(e) => e.key === 'Enter' && handleScrape()}
            />
            <button
              onClick={handleScrape}
              disabled={loading || !url.trim()}
              className="px-6 py-3 rounded-xl bg-secondary text-on-secondary text-label-md flex items-center justify-center gap-2 shadow-glass-lg hover:shadow-[0_8px_32px_rgba(79,70,229,0.3)] transition-all btn-press disabled:opacity-40 whitespace-nowrap"
            >
              {loading ? (
                <span className="material-symbols-outlined animate-spin text-[18px]">progress_activity</span>
              ) : (
                <><span className="material-symbols-outlined text-[18px]">travel_explore</span> ค้นหา</>
              )}
            </button>
          </div>
          {error && <p className="text-label-sm text-error mt-2">{error}</p>}
        </div>

        {/* Results */}
        {result && (
          <div className="max-w-2xl mx-auto p-5 rounded-2xl glass-panel shadow-glass border border-outline-variant/10">
            <div className="flex items-start gap-4">
              {result.images?.[0] && (
                <img
                  src={result.images[0]}
                  alt=""
                  className="w-24 h-24 rounded-xl object-cover bg-surface-container border border-outline-variant/10"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
              )}
              <div className="flex-1 min-w-0">
                <h2 className="text-body-md text-on-surface font-semibold truncate">{result.title || '—'}</h2>
                {result.price && (
                  <p className="text-display-sm text-primary mt-1">{result.price} ฿</p>
                )}
                <p className="text-label-sm text-on-surface-variant mt-0.5">
                  แหล่ง: {result.source}
                </p>
                {result.description && (
                  <p className="text-body-sm text-on-surface-variant mt-2 line-clamp-3">{result.description}</p>
                )}
              </div>
            </div>

            {result.images && result.images.length > 1 && (
              <div className="flex gap-2 mt-4 overflow-x-auto hide-scrollbar">
                {result.images.slice(1).map((img: string, i: number) => (
                  <img
                    key={i}
                    src={img}
                    alt=""
                    className="w-16 h-16 rounded-lg object-cover bg-surface-container border border-outline-variant/10 flex-shrink-0"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                  />
                ))}
              </div>
            )}

            {Object.keys(result.specs || {}).length > 0 && (
              <div className="mt-4 border-t border-outline-variant/10 pt-3">
                <p className="text-label-sm text-on-surface-variant mb-2">สเปก</p>
                {Object.entries(result.specs).map(([k, v]) => (
                  <div key={k} className="flex justify-between py-1 text-body-sm">
                    <span className="text-on-surface-variant">{k}</span>
                    <span className="text-on-surface">{v as string}</span>
                  </div>
                ))}
              </div>
            )}

            <button
              onClick={handleSendToStudio}
              className="mt-4 w-full py-3 rounded-xl bg-gradient-to-r from-secondary to-[#2c248b] text-on-secondary text-label-md flex items-center justify-center gap-2 shadow-glass-lg hover:shadow-[0_8px_32px_rgba(79,70,229,0.3)] transition-all btn-press"
            >
              <span className="material-symbols-outlined text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
              สร้าง UGC ด้วยสินค้านี้
            </button>
          </div>
        )}
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
