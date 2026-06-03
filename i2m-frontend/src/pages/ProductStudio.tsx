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

const STUDIO_STATE_KEY = 'i2m_studio_state'

interface StoredState {
  image: string | null
  productName: string
  productDesc: string
  analysis: AnalysisResult | null
  selectedPreset: string | null
  videoTaskId: string | null
  videoStatus: string | null
  generations: Generation[]
  createdAt: number
}

function loadState(): Partial<StoredState> {
  try {
    const raw = localStorage.getItem(STUDIO_STATE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as StoredState
    // Expire after 2 hours
    if (Date.now() - parsed.createdAt > 2 * 60 * 60 * 1000) {
      localStorage.removeItem(STUDIO_STATE_KEY)
      return {}
    }
    return parsed
  } catch {
    return {}
  }
}

function saveState(state: Partial<StoredState>) {
  try {
    const existing = loadState()
    const merged = { ...existing, ...state, createdAt: Date.now() }
    localStorage.setItem(STUDIO_STATE_KEY, JSON.stringify(merged))
  } catch {
    // localStorage full or blocked
  }
}

export default function ProductStudio() {
  const navigate = useNavigate()
  const location = useLocation()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [initialized, setInitialized] = useState(false)

  // Restore saved state on mount
  const saved = loadState()

  const [image, setImage] = useState<string | null>(saved.image || null)
  const [file, setFile] = useState<File | null>(null)
  const [productName, setProductName] = useState(saved.productName || '')
  const [productDesc, setProductDesc] = useState(saved.productDesc || '')
  const [analyzing, setAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(saved.analysis || null)
  const [selectedPreset, setSelectedPreset] = useState<string | null>(saved.selectedPreset || null)
  const [genImage, setGenImage] = useState(false)
  const [genVideo, setGenVideo] = useState(false)
  const [videoTaskId, setVideoTaskId] = useState<string | null>(saved.videoTaskId || null)
  const [videoStatus, setVideoStatus] = useState<string | null>(saved.videoStatus || null)
  const [error, setError] = useState<string | null>(null)

  const [generations, setGenerations] = useState<Generation[]>(() => {
    const g = saved.generations
    return Array.isArray(g) ? g : []
  })

  // Rehydrate file from blob when image was restored
  useEffect(() => {
    if (saved.image && !file) {
      fetch(saved.image)
        .then(r => r.blob())
        .then(blob => {
          const f = new File([blob], 'product.png', { type: blob.type })
          setFile(f)
        })
        .catch(() => {})
    }
    setInitialized(true)
  }, [])

  // Persist workflow state whenever key fields change
  useEffect(() => {
    if (!initialized) return
    saveState({
      image,
      productName,
      productDesc,
      analysis,
      selectedPreset,
      videoTaskId,
      videoStatus,
      generations,
    })
  }, [image, productName, productDesc, analysis, selectedPreset, videoTaskId, videoStatus, generations, initialized])

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
          setVideoStatus(null)
        } else if (status === 'failed') {
          setError('Video generation failed')
          setGenVideo(false)
          setVideoTaskId(null)
          setVideoStatus(null)
        }
      } catch {
        setError('Video status check failed')
        setGenVideo(false)
        setVideoTaskId(null)
        setVideoStatus(null)
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [videoTaskId])

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
      saveState({ image, productName, productDesc, analysis: result, generations })
    } catch (err: any) {
      setError(err?.message || 'Analysis failed')
    } finally {
      setAnalyzing(false)
    }
  }, [file, productName, productDesc, image, generations])

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
      <main className="flex-1 min-h-screen pt-16 pb-28 md:pt-0 md:pb-0 relative">
        <div className="max-w-container-max mx-auto p-margin-mobile md:p-margin-desktop">

          {/* Header */}
          <header className="mb-6 md:mb-lg">
            <h1 className="font-display text-display-lg-mobile md:text-display-lg text-primary tracking-tight">
              {!analysis ? 'I2M Studio' : analysis.product_name}
            </h1>
            <p className="text-body-lg text-on-surface-variant mt-2 max-w-2xl">
              {!analysis
                ? 'Shape the narrative. Define the environment, subjects, and camera movements for your next sequence.'
                : 'Ready to create content'}
            </p>
          </header>

          {/* Error Banner */}
          {error && (
            <div className="mb-4 px-4 py-3 rounded-xl bg-error-container/40 border border-error/20 text-on-error-container text-body-sm">
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
            /* === UPLOAD + ANALYZE STEP === */
            <div className="flex flex-col gap-md max-w-2xl">

              {/* Upload Zone - glass panel style */}
              <div
                onClick={() => fileInputRef.current?.click()}
                className={`relative rounded-2xl overflow-hidden cursor-pointer transition-all duration-300 glass-panel ${
                  image ? '' : 'border-2 border-dashed border-outline-variant/30 hover:border-secondary/40'
                }`}
              >
                <input ref={fileInputRef} type="file" accept="image/*" onChange={handleUpload} className="hidden" />
                {image ? (
                  <div className="relative group">
                    <img src={image} alt="Product" className="w-full max-h-[400px] object-contain p-4" />
                    <button
                      onClick={(e) => { e.stopPropagation(); setImage(null); setFile(null) }}
                      className="absolute top-3 right-3 w-9 h-9 rounded-full bg-white/80 backdrop-blur flex items-center justify-center shadow-lg hover:bg-white transition-all"
                    >
                      <span className="material-symbols-outlined text-[20px]">close</span>
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-16 gap-4">
                    <div className="w-16 h-16 rounded-2xl bg-secondary/10 flex items-center justify-center">
                      <span className="material-symbols-outlined text-[32px] text-secondary" style={{ fontVariationSettings: "'FILL' 1" }}>add_photo_alternate</span>
                    </div>
                    <p className="text-headline-sm text-primary">Upload Product Photo</p>
                    <p className="text-body-md text-on-surface-variant">Tap to upload or drag and drop</p>
                    <div className="flex gap-2">
                      <span className="px-3 py-1 rounded-full bg-surface-container-low text-label-sm text-on-surface-variant">JPG</span>
                      <span className="px-3 py-1 rounded-full bg-surface-container-low text-label-sm text-on-surface-variant">PNG</span>
                      <span className="px-3 py-1 rounded-full bg-surface-container-low text-label-sm text-on-surface-variant">WEBP</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Product Info - glass panel */}
              <div className="glass-panel rounded-2xl p-md flex flex-col gap-lg">
                <section className="flex flex-col gap-sm">
                  <label className="text-label-md text-on-surface uppercase tracking-widest">Product Name</label>
                  <input
                    type="text"
                    value={productName}
                    onChange={(e) => setProductName(e.target.value)}
                    placeholder="e.g., SPF50 Sunscreen"
                    className="w-full px-4 py-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-body-md text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:ring-2 focus:ring-secondary/40 transition-all"
                  />
                </section>
                <section className="flex flex-col gap-sm">
                  <label className="text-label-md text-on-surface uppercase tracking-widest">Description (optional)</label>
                  <textarea
                    value={productDesc}
                    onChange={(e) => setProductDesc(e.target.value)}
                    placeholder="Key features, target audience, unique selling points..."
                    rows={3}
                    className="w-full px-4 py-3 rounded-xl bg-surface-container-low border border-outline-variant/30 text-body-md text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none focus:ring-2 focus:ring-secondary/40 transition-all resize-none"
                  />
                </section>
              </div>

              {/* Analyze Button */}
              <button
                onClick={handleAnalyze}
                disabled={analyzing || !file || !productName.trim()}
                className="w-full py-4 rounded-xl bg-gradient-to-r from-secondary to-[#2c248b] text-on-secondary text-headline-sm flex items-center justify-center gap-2 shadow-[0_8px_32px_rgba(79,70,229,0.25)] hover:shadow-[0_12px_40px_rgba(79,70,229,0.4)] hover:-translate-y-0.5 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed btn-press"
              >
                {analyzing ? (
                  <><span className="material-symbols-outlined animate-spin">progress_activity</span> Analyzing...</>
                ) : (
                  <><span className="material-symbols-outlined">auto_awesome</span> Initialize Analysis</>
                )}
              </button>
            </div>
          ) : (
            /* === RESULTS VIEW === */
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-md md:gap-xl">

              {/* Left - Editor Core */}
              <div className="lg:col-span-8 flex flex-col gap-lg">

                {/* Product Info Card - glass */}
                <div className="glass-panel rounded-2xl p-md">
                  <div className="flex items-start gap-4">
                    {image && (
                      <img src={image} alt={analysis.product_name} className="w-16 h-16 rounded-xl object-cover flex-shrink-0 border border-outline-variant/20" />
                    )}
                    <div className="flex-1 min-w-0">
                      <h2 className="text-headline-sm text-primary">{analysis.product_name}</h2>
                      <p className="text-body-sm text-on-surface-variant mt-1 line-clamp-2">{analysis.product_desc}</p>
                      {(analysis.seo_keywords || []).slice(0, 3).map(kw => (
                        <span key={kw} className="inline-block mt-2 mr-1.5 px-2 py-0.5 rounded-full bg-secondary/10 text-secondary text-label-sm">{kw}</span>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Preset Styles - Aether Carousel */}
                <section className="flex flex-col gap-sm overflow-hidden">
                  <div className="flex justify-between items-center">
                    <h3 className="text-label-md text-on-surface uppercase tracking-widest">Image Presets</h3>
                    <span className="text-label-sm text-secondary/70 bg-secondary/10 px-2 py-1 rounded-full">v4 Engine Ready</span>
                  </div>
                  <div className="flex gap-md overflow-x-auto hide-scrollbar pb-4 snap-x">
                    {presetStyles.map(ps => (
                      <button
                        key={ps.id}
                        onClick={() => setSelectedPreset(ps.id)}
                        className={`snap-start flex-shrink-0 w-40 md:w-48 text-left group focus:outline-none ${
                          selectedPreset === ps.id ? 'relative' : ''
                        }`}
                      >
                        <div className={`relative aspect-[4/5] rounded-xl overflow-hidden mb-3 transition-all ${
                          selectedPreset === ps.id
                            ? 'ring-2 ring-secondary shadow-[0_4px_20px_rgba(79,70,229,0.15)] border border-secondary/30'
                            : 'border border-outline-variant/20 shadow-sm group-hover:shadow-md group-hover:border-secondary/30'
                        }`}>
                          <div className="w-full h-full bg-gradient-to-br from-secondary/5 via-surface-variant to-secondary/10 flex items-center justify-center">
                            <span className="text-4xl">{ps.label.split(' ')[0]}</span>
                          </div>
                          {selectedPreset === ps.id && (
                            <div className="absolute top-2 right-2 bg-secondary text-on-secondary rounded-full p-1 shadow-md">
                              <span className="material-symbols-outlined text-[16px]" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                            </div>
                          )}
                        </div>
                        <span className={`text-label-md block px-1 ${selectedPreset === ps.id ? 'text-secondary font-bold' : 'text-on-surface'}`}>{ps.label}</span>
                        <span className="text-label-sm text-on-surface-variant block px-1">{ps.desc}</span>
                      </button>
                    ))}
                  </div>
                </section>

                {/* AI Script Section */}
                <div className="glass-panel rounded-2xl p-md">
                  <h3 className="text-label-md text-on-surface uppercase tracking-widest mb-4">AI Script</h3>
                  <div className="flex flex-col gap-3">
                    {(analysis.hooks || []).slice(0, 3).map((hook, i) => (
                      <div key={i} className="flex items-start gap-2 text-body-sm text-on-surface-variant">
                        <span className="text-secondary font-medium">Hook {i+1}:</span>
                        <span>{hook}</span>
                      </div>
                    ))}
                  </div>
                  {analysis.copy && (
                    <div className="mt-4 pt-4 border-t border-outline-variant/20">
                      <p className="text-label-sm text-on-surface-variant mb-2">Marketing Copy:</p>
                      <p className="text-body-md text-on-surface">{analysis.copy}</p>
                    </div>
                  )}
                </div>

                {/* Recent Generations */}
                {generations.length > 0 && (
                  <section>
                    <div className="flex justify-between items-center mb-3">
                      <h3 className="text-label-md text-on-surface uppercase tracking-widest">Recent Outputs</h3>
                      <button onClick={() => navigate('/gallery')} className="text-label-sm text-secondary hover:underline flex items-center gap-1">
                        View All <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
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
                  className="self-start flex items-center gap-1 px-4 py-2 rounded-xl text-body-sm text-on-surface-variant hover:text-on-surface bg-surface-container hover:bg-surface-container-high transition-colors"
                >
                  <span className="material-symbols-outlined text-[16px]">arrow_back</span>
                  Start Over
                </button>
              </div>

              {/* Right - Parameters Sidebar */}
              <div className="lg:col-span-4 flex flex-col gap-lg lg:pl-md">

                {/* Generate Panel - glass */}
                <div className="glass-panel rounded-2xl p-md flex flex-col gap-lg shadow-[0_4px_24px_rgba(79,70,229,0.03)]">

                  {/* Generate Image */}
                  <section className="flex flex-col gap-sm">
                    <h3 className="text-label-md text-on-surface uppercase tracking-widest flex items-center gap-2">
                      <span className="material-symbols-outlined text-[18px]">image</span> Image Generation
                    </h3>
                    <button
                      onClick={handleGenerateImage}
                      disabled={genImage || !selectedPreset}
                      className="w-full py-4 rounded-xl bg-gradient-to-r from-secondary to-[#2c248b] text-on-secondary text-headline-sm flex items-center justify-center gap-2 shadow-[0_8px_32px_rgba(79,70,229,0.25)] hover:shadow-[0_12px_40px_rgba(79,70,229,0.4)] hover:-translate-y-0.5 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed btn-press"
                    >
                      {genImage ? (
                        <><span className="material-symbols-outlined animate-spin">progress_activity</span> Generating...</>
                      ) : (
                        <><span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span> Generate Image</>
                      )}
                    </button>
                  </section>

                  <hr className="border-outline-variant/20" />

                  {/* Generate Video */}
                  <section className="flex flex-col gap-sm">
                    <h3 className="text-label-md text-on-surface uppercase tracking-widest flex items-center gap-2">
                      <span className="material-symbols-outlined text-[18px]">videocam</span> Video Sequence
                    </h3>
                    {videoTaskId && (
                      <div className="p-3 rounded-xl bg-secondary/5 border border-secondary/20 mb-2">
                        <div className="flex items-center gap-3">
                          <span className="material-symbols-outlined text-secondary animate-pulse">pending</span>
                          <div className="flex-1">
                            <p className="text-body-sm font-medium">Processing...</p>
                            <div className="mt-2 h-1.5 rounded-full bg-surface-container overflow-hidden">
                              <div className="h-full rounded-full bg-secondary/60 animate-pulse" style={{ width: '60%' }} />
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                    <button
                      onClick={handleGenerateVideo}
                      disabled={genVideo || !image}
                      className="w-full py-4 rounded-xl bg-gradient-to-r from-secondary/90 to-secondary text-on-secondary text-headline-sm flex items-center justify-center gap-2 shadow-[0_8px_32px_rgba(79,70,229,0.25)] hover:shadow-[0_12px_40px_rgba(79,70,229,0.4)] hover:-translate-y-0.5 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed btn-press"
                    >
                      {genVideo ? (
                        <><span className="material-symbols-outlined animate-spin">progress_activity</span> {videoStatus === 'queued' ? 'Queued...' : 'Generating...'}</>
                      ) : (
                        <><span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>bolt</span> Generate Video</>
                      )}
                    </button>
                  </section>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Mobile Bottom Tab Bar - Aether style */}
      <nav className="md:hidden bg-surface/80 backdrop-blur-2xl fixed bottom-0 w-full z-50 border-t border-outline-variant/10 shadow-[0_-4px_20px_rgba(79,70,229,0.08)] flex justify-around items-center h-20 px-4">
        <button
          onClick={() => navigate('/profile')}
          className={`flex flex-col items-center justify-center active:scale-90 transition-transform ${
            currentTab === 'profile' ? 'text-secondary' : 'text-on-surface-variant hover:text-secondary'
          }`}
        >
          <span className="material-symbols-outlined mb-0.5 group-hover:scale-110 transition-transform"
            style={{ fontVariationSettings: currentTab === 'profile' ? "'FILL' 1" : "'FILL' 0" }}
          >person</span>
          <span className="text-label-sm">Profile</span>
        </button>
        <button
          onClick={() => navigate('/')}
          className={`flex flex-col items-center justify-center bg-secondary-container/20 rounded-full px-5 py-1 active:scale-90 transition-transform ${
            currentTab === 'studio' ? 'text-secondary' : 'text-on-surface-variant'
          }`}
        >
          <span className="material-symbols-outlined mb-0.5"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >add_circle</span>
          <span className="text-label-sm font-bold">Create</span>
        </button>
        <button
          onClick={() => navigate('/gallery')}
          className={`flex flex-col items-center justify-center active:scale-90 transition-transform ${
            currentTab === 'gallery' ? 'text-secondary' : 'text-on-surface-variant hover:text-secondary'
          }`}
        >
          <span className="material-symbols-outlined mb-0.5"
            style={{ fontVariationSettings: currentTab === 'gallery' ? "'FILL' 1" : "'FILL' 0" }}
          >video_library</span>
          <span className="text-label-sm">Library</span>
        </button>
      </nav>

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
