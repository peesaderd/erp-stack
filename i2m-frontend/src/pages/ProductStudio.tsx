import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import api from '../lib/api'

interface AnalysisResult {
  image_prompts: Record<string, string>
  video_prompt: string
  hooks: string[]
  copy: string
  seo_keywords: string[]
  product_name: string
  product_desc: string
}

interface Generation {
  id: string
  type: 'image' | 'video'
  url: string
  prompt: string
  style?: string
  createdAt: number
}

const presetStyles = [
  { id: 'holding_product',   label: '🖐️ ถือสินค้า',   desc: 'ถือสินค้าในมือธรรมชาติ' },
  { id: 'product_usage',     label: '📱 สาธิตการใช้',  desc: 'กำลังใช้งานจริง' },
  { id: 'lifestyle',         label: '🌿 ไลฟ์สไตล์',    desc: 'ในบรรยากาศการใช้ชีวิต' },
  { id: 'close_up',          label: '🔍 ใกล้ชิด',       desc: 'มุมชัด Detail สินค้า' },
  { id: 'review_style',      label: '🎬 Review',        desc: 'สไตล์รีวิว' },
]

export default function ProductStudio() {
  const navigate = useNavigate()
  const location = useLocation()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [image, setImage] = useState<string | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [productName, setProductName] = useState('')
  const [productDesc, setProductDesc] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null)
  const [genImage, setGenImage] = useState(false)
  const [genVideo, setGenVideo] = useState(false)
  const [videoTaskId, setVideoTaskId] = useState<string | null>(null)
  const [videoStatus, setVideoStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Generations stored in state + localStorage
  const [generations, setGenerations] = useState<Generation[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('i2m_generations') || '[]')
    } catch {
      return []
    }
  })

  useEffect(() => {
    localStorage.setItem('i2m_generations', JSON.stringify(generations))
  }, [generations])

  // Poll video status
  useEffect(() => {
    if (!videoTaskId || videoStatus === 'completed' || videoStatus === 'failed') return
    const interval = setInterval(async () => {
      try {
        const res = await api.getVideoResult(videoTaskId)
        const status = res.status || res.data?.status
        setVideoStatus(status)
        if (status === 'completed' && res.url) {
          setGenerations(prev => [...prev, {
            id: Date.now().toString(),
            type: 'video',
            url: res.url,
            prompt: '',
            createdAt: Date.now(),
          }])
          setGenVideo(false)
          setVideoTaskId(null)
        } else if (status === 'failed') {
          setError('Video generation failed')
          setGenVideo(false)
          setVideoTaskId(null)
        }
      } catch {
        setVideoStatus('failed')
        setGenVideo(false)
        setVideoTaskId(null)
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [videoTaskId, videoStatus])

  const handleUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    setFile(f)
    setError(null)
    setAnalysis(null)
    setSelectedPreset(null)

    const reader = new FileReader()
    reader.onload = (ev) => setImage(ev.target?.result as string)
    reader.readAsDataURL(f)
  }, [])

  const handleAnalyze = useCallback(async () => {
    if (!file || !productName.trim()) {
      setError('Please upload a photo and enter product name')
      return
    }
    setAnalyzing(true)
    setError(null)
    try {
      const result = await api.analyzeProduct(file, productName, productDesc)
      setAnalysis(result)
    } catch (err: any) {
      setError(err?.message || 'Analysis failed')
    } finally {
      setAnalyzing(false)
    }
  }, [file, productName, productDesc])

  const handleGenerateImage = useCallback(async () => {
    if (!analysis || !selectedPreset) return
    setGenImage(true)
    setError(null)
    try {
      const prompt = analysis.image_prompts[selectedPreset] || analysis.image_prompts.default
      const result = await api.generateImage(prompt, productName)
      if (result.url) {
        setGenerations(prev => [...prev, {
          id: Date.now().toString(),
          type: 'image',
          url: result.url,
          prompt,
          style: selectedPreset,
          createdAt: Date.now(),
        }])
      }
    } catch (err: any) {
      setError(err?.message || 'Image generation failed')
    } finally {
      setGenImage(false)
    }
  }, [analysis, selectedPreset, productName])

  const handleGenerateVideo = useCallback(async () => {
    if (!analysis || !image) return
    setGenVideo(true)
    setError(null)
    setVideoStatus('queued')
    try {
      const result = await api.generateVideo(analysis.video_prompt, image, productName)
      setVideoTaskId(result.task_id || result.id)
    } catch (err: any) {
      setError(err?.message || 'Video generation failed')
      setGenVideo(false)
    }
  }, [analysis, image, productName])

  const currentTab = location.pathname === '/' ? 'studio' : location.pathname === '/gallery' ? 'gallery' : 'profile'

  return (
    <>
      {/* Main Content Area */}
      <main className="flex-1 min-h-screen pt-16 pb-28 md:pt-0 md:pb-0 relative">
        <div className="max-w-container-max mx-auto p-margin-mobile md:p-margin-desktop">
          
          {/* Page Header */}
          <header className="mb-6">
            <h1 className="text-display-sm md:text-display-md text-primary tracking-tight">
              {!analysis ? 'I2M Studio' : analysis.product_name}
            </h1>
            <p className="text-body-lg text-on-surface-variant mt-1">
              {!analysis ? 'อัปโหลดสินค้า → AI วิเคราะห์ → สร้างรูป + วิดีโอ' : 'พร้อมสร้างคอนเทนต์'}
            </p>
          </header>

          {/* Error Banner */}
          {error && (
            <div className="mb-4 px-4 py-3 rounded-xl bg-error-container/40 border-l-4 border-error text-on-error-container text-body-sm">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-[18px]">error</span>
                <span>{error}</span>
                <button onClick={() => setError(null)} className="ml-auto text-on-error-container/60 hover:text-on-error-container">
                  <span className="material-symbols-outlined text-[18px]">close</span>
                </button>
              </div>
            </div>
          )}

          {!analysis ? (
            /* Upload + Analyze Step */
            <div className="flex flex-col gap-6 max-w-2xl">
              {/* Hero Upload Zone */}
              <div
                onClick={() => fileInputRef.current?.click()}
                className={`relative rounded-3xl overflow-hidden cursor-pointer transition-all duration-500 ${
                  image 
                    ? 'border border-outline-variant/20 shadow-glass-lg' 
                    : 'border-2 border-dashed border-primary/20 hover:border-primary/40 hover:shadow-[0_8px_40px_rgba(79,70,229,0.08)]'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleUpload}
                  className="hidden"
                />
                {image ? (
                  <div className="relative group">
                    <img src={image} alt="Product" className="w-full max-h-[400px] object-contain bg-gradient-to-b from-surface-variant/30 to-surface p-4" />
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/5 transition-colors duration-300" />
                    <button
                      onClick={(e) => { e.stopPropagation(); setImage(null); setFile(null) }}
                      className="absolute top-3 right-3 w-9 h-9 rounded-full bg-white/80 backdrop-blur-md flex items-center justify-center shadow-lg hover:bg-white transition-all duration-200 ios-spring"
                    >
                      <span className="material-symbols-outlined text-[20px] text-on-surface">close</span>
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-20 gap-4 bg-gradient-to-b from-primary/5 via-transparent to-surface-variant/20">
                    <div className="w-20 h-20 rounded-full bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center shadow-inner">
                      <span className="material-symbols-outlined text-[40px] text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>add_photo_alternate</span>
                    </div>
                    <div className="text-center">
                      <p className="text-headline-sm text-primary font-semibold">เริ่มต้นด้วยรูปสินค้า</p>
                      <p className="text-body-md text-on-surface-variant mt-1">แตะเพื่ออัปโหลด หรือลากรูปมาใส่</p>
                    </div>
                    <div className="flex gap-2 mt-2">
                      <span className="px-3 py-1 rounded-full bg-surface-container-low text-label-sm text-on-surface-variant border border-outline-variant/20">JPG</span>
                      <span className="px-3 py-1 rounded-full bg-surface-container-low text-label-sm text-on-surface-variant border border-outline-variant/20">PNG</span>
                      <span className="px-3 py-1 rounded-full bg-surface-container-low text-label-sm text-on-surface-variant border border-outline-variant/20">WEBP</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Product Info */}
              <div className="flex flex-col gap-4">
                <div>
                  <label className="text-label-md text-on-surface uppercase tracking-widest mb-2 block">ชื่อสินค้า</label>
                  <input
                    type="text"
                    value={productName}
                    onChange={(e) => setProductName(e.target.value)}
                    placeholder="เช่น ครีมกันแดด SPF50"
                    className="w-full px-4 py-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-body-md text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:ring-2 focus:ring-secondary/40 transition-all glass-panel"
                  />
                </div>
                <div>
                  <label className="text-label-md text-on-surface uppercase tracking-widest mb-2 block">รายละเอียด (optional)</label>
                  <textarea
                    value={productDesc}
                    onChange={(e) => setProductDesc(e.target.value)}
                    placeholder="รายละเอียดเพิ่มเติม เช่น คุณสมบัติเด่น กลุ่มเป้าหมาย..."
                    rows={3}
                    className="w-full px-4 py-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-body-md text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:ring-2 focus:ring-secondary/40 transition-all glass-panel resize-none"
                  />
                </div>
                <button
                  onClick={handleAnalyze}
                  disabled={analyzing || !file || !productName.trim()}
                  className="w-full py-4 rounded-xl bg-primary text-on-primary text-headline-sm flex items-center justify-center gap-2 shadow-[0_8px_32px_rgba(79,70,229,0.25)] hover:shadow-[0_12px_40px_rgba(79,70,229,0.4)] hover:-translate-y-0.5 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed btn-press"
                >
                  {analyzing ? (
                    <>
                      <span className="material-symbols-outlined animate-spin">progress_activity</span>
                      กำลังวิเคราะห์...
                    </>
                  ) : (
                    <>
                      <span className="material-symbols-outlined">auto_awesome</span>
                      เริ่มวิเคราะห์
                    </>
                  )}
                </button>
              </div>
            </div>
          ) : (
            /* Results View */
            <div className="flex flex-col gap-6">
              {/* Product Info Card */}
              <div className="p-5 rounded-2xl glass-panel shadow-glass border border-outline-variant/10">
                <div className="flex items-start gap-4">
                  {image && (
                    <img src={image} alt={analysis.product_name} className="w-16 h-16 rounded-xl object-cover flex-shrink-0 border border-outline-variant/20" />
                  )}
                  <div className="flex-1 min-w-0">
                    <h2 className="text-headline-sm text-primary">{analysis.product_name}</h2>
                    <p className="text-body-sm text-on-surface-variant mt-1 line-clamp-2">{analysis.product_desc}</p>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {(analysis.seo_keywords || []).slice(0, 3).map(kw => (
                        <span key={kw} className="px-2 py-0.5 rounded-full bg-secondary/10 text-secondary text-label-sm">{kw}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Preset Styles Carousel */}
              <section>
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-label-md text-on-surface uppercase tracking-widest">Preset สร้างรูป</h3>
                </div>
                <div className="flex gap-3 overflow-x-auto hide-scrollbar pb-2 snap-x">
                  {presetStyles.map(ps => (
                    <button
                      key={ps.id}
                      onClick={() => setSelectedPreset(ps.id)}
                      className={`snap-start flex-shrink-0 w-36 p-4 rounded-xl text-left transition-all duration-200 border ${
                        selectedPreset === ps.id
                          ? 'bg-secondary/10 border-secondary/30 ring-2 ring-secondary/30 shadow-glass-lg'
                          : 'bg-surface-container-low border-outline-variant/20 hover:bg-surface-container hover:shadow-glass'
                      }`}
                    >
                      <p className="text-lg mb-1">{ps.label.split(' ')[0]}</p>
                      <p className="text-body-sm text-on-surface-variant">{ps.desc}</p>
                    </button>
                  ))}
                </div>
              </section>

              {/* Generate Buttons */}
              <div className="flex flex-col sm:flex-row gap-3">
                <button
                  onClick={handleGenerateImage}
                  disabled={genImage || !selectedPreset}
                  className="flex-1 py-4 rounded-xl bg-gradient-to-r from-primary to-[#6366f1] text-on-primary text-headline-sm flex items-center justify-center gap-2 shadow-glass-lg hover:shadow-[0_12px_40px_rgba(79,70,229,0.4)] hover:-translate-y-0.5 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed btn-press"
                >
                  {genImage ? (
                    <><span className="material-symbols-outlined animate-spin">progress_activity</span> กำลังสร้าง...</>
                  ) : (
                    <><span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>image</span> สร้างรูป</>
                  )}
                </button>
                <button
                  onClick={handleGenerateVideo}
                  disabled={genVideo || !image}
                  className="flex-1 py-4 rounded-xl bg-primary-container text-on-primary text-headline-sm flex items-center justify-center gap-2 shadow-glass-lg hover:shadow-[0_12px_40px_rgba(79,70,229,0.4)] hover:-translate-y-0.5 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed btn-press"
                >
                  {genVideo ? (
                    <><span className="material-symbols-outlined animate-spin">progress_activity</span> {videoStatus === 'queued' ? 'รอคิว...' : 'กำลังสร้าง...'}</>
                  ) : (
                    <><span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>videocam</span> สร้างวิดีโอ</>
                  )}
                </button>
              </div>

              {/* Video Status */}
              {videoTaskId && (
                <div className="p-4 rounded-xl bg-secondary/5 border border-secondary/20">
                  <div className="flex items-center gap-3">
                    <span className="material-symbols-outlined text-secondary animate-pulse">pending</span>
                    <div className="flex-1">
                      <p className="text-body-sm font-medium">กำลังประมวลผลวิดีโอ...</p>
                      <div className="mt-2 h-1.5 rounded-full bg-surface-container overflow-hidden">
                        <div className="h-full rounded-full bg-secondary/60 animate-pulse" style={{ width: '60%' }} />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Hooks / Copy */}
              <div className="p-5 rounded-2xl glass-panel shadow-glass border border-outline-variant/10">
                <h3 className="text-label-md text-on-surface uppercase tracking-widest mb-3">AI Script</h3>
                <div className="flex flex-col gap-2">
                  {(analysis.hooks || []).slice(0, 3).map((hook, i) => (
                    <div key={i} className="flex items-start gap-2 text-body-sm text-on-surface-variant">
                      <span className="text-secondary font-medium">Hook {i+1}:</span>
                      <span>{hook}</span>
                    </div>
                  ))}
                </div>
                {analysis.copy && (
                  <div className="mt-3 pt-3 border-t border-outline-variant/20">
                    <p className="text-label-sm text-on-surface-variant mb-1">AI Copy:</p>
                    <p className="text-body-sm text-on-surface">{analysis.copy}</p>
                  </div>
                )}
              </div>

              {/* Recent Generations */}
              {generations.length > 0 && (
                <section>
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="text-label-md text-on-surface uppercase tracking-widest">ผลงานล่าสุด</h3>
                    <button onClick={() => navigate('/gallery')} className="text-label-sm text-secondary hover:underline flex items-center gap-1">
                      ดูทั้งหมด <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
                    </button>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    {generations.slice().reverse().slice(0, 6).map(gen => (
                      <div key={gen.id} className="aspect-square rounded-xl overflow-hidden bg-surface-container border border-outline-variant/10 relative group">
                        {gen.type === 'image' ? (
                          <img src={gen.url} alt="" className="w-full h-full object-cover" />
                        ) : (
                          <video src={gen.url} className="w-full h-full object-cover" muted />
                        )}
                        <div className="absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase bg-surface/70 backdrop-blur text-on-surface-variant">
                          {gen.type}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Reset */}
              <button
                onClick={() => { setAnalysis(null); setSelectedPreset(null); setVideoTaskId(null); setVideoStatus(null) }}
                className="self-start px-4 py-2 rounded-xl text-body-sm text-on-surface-variant hover:text-on-surface bg-surface-container hover:bg-surface-container-high transition-colors"
              >
                ← เริ่มใหม่
              </button>
            </div>
          )}
        </div>
      </main>

      {/* Bottom Tab Bar */}
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
                currentTab === tab.path.replace('/', '') || (tab.path === '/' && currentTab === 'studio')
                  ? 'text-secondary bg-secondary-container/20'
                  : 'text-on-surface-variant hover:text-secondary'
              }`}
            >
              <span className="material-symbols-outlined text-[24px]" style={{ fontVariationSettings: currentTab === (tab.path.replace('/', '') || 'studio') ? "'FILL' 1" : "'FILL' 0" }}>{tab.icon}</span>
              <span className="text-label-sm">{tab.label}</span>
            </button>
          ))}
        </div>
      </nav>

      {/* Desktop Sidebar */}
      <nav className="hidden md:flex flex-col h-full w-72 rounded-r-2xl bg-surface dark:bg-surface-container divide-y divide-outline-variant/10 shadow-xl fixed left-0 top-0 bottom-0 z-40 p-6 transition-all duration-200">
        <div className="flex items-center gap-3 pb-6">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary to-[#6366f1] flex items-center justify-center text-on-primary">
            <span className="material-symbols-outlined text-[28px]" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
          </div>
          <div>
            <h2 className="text-headline-sm text-primary">I2M Studio</h2>
            <p className="text-label-sm text-on-surface-variant">Content Creator</p>
          </div>
        </div>
        <div className="flex-1 py-6 space-y-1">
          {[
            { path: '/', icon: 'auto_awesome', label: 'Studio' },
            { path: '/gallery', icon: 'grid_view', label: 'Gallery' },
            { path: '/profile', icon: 'person', label: 'Profile' },
          ].map(tab => (
            <button
              key={tab.path}
              onClick={() => navigate(tab.path)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 text-left ${
                (tab.path === '/' && currentTab === 'studio') || currentTab === tab.path.replace('/', '')
                  ? 'bg-secondary/10 text-secondary font-bold'
                  : 'text-on-surface-variant hover:bg-surface-variant hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined" style={{ fontVariationSettings: (currentTab === (tab.path.replace('/', '') || 'studio')) ? "'FILL' 1" : "'FILL' 0" }}>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
        <div className="pt-6 text-label-sm text-on-surface-variant/60 text-center">
          I2M Studio v1.0
        </div>
      </nav>
    </>
  )
}
