import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../lib/api'

interface GalleryItem {
  id: string
  type: 'image' | 'video'
  url: string
  prompt?: string
  style?: string
  createdAt: number
}

export default function ImageGallery() {
  const navigate = useNavigate()
  const [items] = useState<GalleryItem[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('i2m_generations') || '[]')
    } catch { return [] }
  })
  const [viewItem, setViewItem] = useState<GalleryItem | null>(null)
  const [exporting, setExporting] = useState(false)
  const [exportMsg, setExportMsg] = useState<string | null>(null)

  const handleExport = async (item: GalleryItem) => {
    setExporting(true)
    setExportMsg(null)
    try {
      const res = await api.exportToChannel(item.url, item.type, item.prompt || '')
      setExportMsg('ส่งออกแล้ว!')
      setTimeout(() => setExportMsg(null), 2000)
    } catch (err: any) {
      setExportMsg(err?.message || 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  const handleClearAll = () => {
    if (confirm('Clear all gallery items?')) {
      localStorage.removeItem('i2m_generations')
      window.location.reload()
    }
  }

  // Sort newest first
  const sorted = [...items].reverse()

  return (
    <div className="min-h-screen bg-background pb-28 md:pb-0 md:pl-72">
      {/* Desktop Header */}
      <div className="hidden md:block max-w-container-max mx-auto p-margin-desktop pb-0">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-headline-md text-primary tracking-tight">Gallery</h1>
            <p className="text-body-lg text-on-surface-variant mt-1">{items.length} items</p>
          </div>
          {items.length > 0 && (
            <button onClick={handleClearAll} className="px-4 py-2 rounded-xl text-label-md text-on-surface-variant hover:text-error bg-surface-container hover:bg-surface-container-high transition-colors">
              Clear All
            </button>
          )}
        </div>
      </div>

      <div className="max-w-container-max mx-auto p-margin-mobile md:p-margin-desktop">
        {/* Mobile Header */}
        <div className="md:hidden flex items-center justify-between mb-4">
          <div>
            <h1 className="text-display-sm text-primary tracking-tight">Gallery</h1>
            <p className="text-body-sm text-on-surface-variant">{items.length} items</p>
          </div>
          {items.length > 0 && (
            <button onClick={handleClearAll} className="px-3 py-1.5 rounded-lg text-label-sm text-on-surface-variant hover:text-error bg-surface-container transition-colors">
              Clear
            </button>
          )}
        </div>

        {sorted.length === 0 ? (
          /* Empty State */
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <div className="w-20 h-20 rounded-full bg-secondary/10 flex items-center justify-center">
              <span className="material-symbols-outlined text-[40px] text-secondary/40" style={{ fontVariationSettings: "'FILL' 1" }}>gallery_thumbnail</span>
            </div>
            <p className="text-headline-sm text-on-surface-variant">ยังไม่มีผลงาน</p>
            <p className="text-body-md text-on-surface-variant/60">สร้างรูปหรือวิดีโอแล้วจะมาโผล่ที่นี่</p>
            <button
              onClick={() => navigate('/')}
              className="mt-2 px-6 py-3 rounded-xl bg-secondary text-on-secondary text-body-md flex items-center gap-2 shadow-glass-lg hover:shadow-[0_8px_32px_rgba(79,70,229,0.3)] transition-all duration-200 btn-press"
            >
              <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>add</span>
              เริ่มสร้าง
            </button>
          </div>
        ) : (
          /* Grid */
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {sorted.map(item => (
              <div
                key={item.id}
                onClick={() => setViewItem(item)}
                className="aspect-square rounded-2xl overflow-hidden bg-surface-container border border-outline-variant/10 relative group cursor-pointer hover:shadow-card-hover transition-all duration-300"
              >
                {item.type === 'image' ? (
                  <img src={item.url} alt="" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" loading="lazy" />
                ) : (
                  <video src={item.url} className="w-full h-full object-cover" muted />
                )}
                <div className="absolute inset-0 bg-gradient-to-t from-primary/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                  <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between">
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase bg-surface/70 backdrop-blur text-on-surface glass-panel">
                      {item.type}
                    </span>
                    {item.style && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-secondary/70 backdrop-blur text-on-secondary truncate max-w-[100px] glass-panel">
                        {item.style}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {viewItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4" onClick={() => setViewItem(null)}>
          <div className="w-full max-w-2xl bg-surface rounded-2xl overflow-hidden shadow-2xl border border-outline-variant/10" onClick={e => e.stopPropagation()}>
            <div className="p-4">
              {viewItem.type === 'image' ? (
                <img src={viewItem.url} alt="" className="w-full rounded-xl" />
              ) : (
                <video src={viewItem.url} controls className="w-full rounded-xl" />
              )}
            </div>
            <div className="px-4 pb-4 flex flex-col gap-2">
              {viewItem.prompt && (
                <p className="text-body-sm text-on-surface-variant line-clamp-2">{viewItem.prompt}</p>
              )}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleExport(viewItem)}
                  disabled={exporting}
                  className="flex-1 py-3 rounded-xl bg-secondary text-on-secondary text-label-md flex items-center justify-center gap-2 transition-all btn-press disabled:opacity-50"
                >
                  {exporting ? (
                    <span className="material-symbols-outlined animate-spin text-[18px]">progress_activity</span>
                  ) : (
                    <><span className="material-symbols-outlined text-[18px]">ios_share</span> ส่งออก</>
                  )}
                </button>
                <a
                  href={viewItem.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 py-3 rounded-xl border border-outline-variant/30 text-label-md flex items-center justify-center gap-2 hover:bg-surface-variant transition-all"
                >
                  <span className="material-symbols-outlined text-[18px]">open_in_new</span>
                  เปิด
                </a>
              </div>
              {exportMsg && (
                <p className="text-label-sm text-center mt-1" style={{ color: exportMsg === 'ส่งออกแล้ว!' ? 'var(--color-success)' : 'var(--color-error)' }}>
                  {exportMsg}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

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
                tab.path === '/gallery' ? 'text-secondary bg-secondary-container/20' : 'text-on-surface-variant hover:text-secondary'
              }`}
            >
              <span className="material-symbols-outlined text-[24px]" style={{ fontVariationSettings: tab.path === '/gallery' ? "'FILL' 1" : "'FILL' 0" }}>{tab.icon}</span>
              <span className="text-label-sm">{tab.label}</span>
            </button>
          ))}
        </div>
      </nav>
    </div>
  )
}
