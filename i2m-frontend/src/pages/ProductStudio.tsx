import { useState, useRef } from 'react'
import { api } from '../lib/api'

interface ImagePrompt {
  id: string
  name: string
  prompt: string
}

interface AnalysisResult {
  image_prompts: ImagePrompt[]
  video_prompt: string
  hook_suggestions: string[]
  marketing_copy: string
  hashtags: string[]
}

type WorkflowStep = 'input' | 'analyzed' | 'images_ready' | 'video_ready'

export default function ProductStudio() {
  const [productName, setProductName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('')
  const [targetAudience, setTargetAudience] = useState('')
  const [productImage, setProductImage] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [step, setStep] = useState<WorkflowStep>('input')
  const [loading, setLoading] = useState(false)
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)

  // Image generation states
  const [selectedPreset, setSelectedPreset] = useState<string>('holding_product')
  const [editablePrompt, setEditablePrompt] = useState('')
  const [generatedImages, setGeneratedImages] = useState<string[]>([])
  const [genLoading, setGenLoading] = useState(false)

  // Video states
  const [videoPrompt, setVideoPrompt] = useState('')
  const [selectedImage, setSelectedImage] = useState<string | null>(null)
  const [videoTaskId, setVideoTaskId] = useState<string | null>(null)
  const [videoStatus, setVideoStatus] = useState<string>('')
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [videoLoading, setVideoLoading] = useState(false)

  // Handle image upload
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => setProductImage(ev.target?.result as string)
    reader.readAsDataURL(file)
  }

  // Analyze product
  const handleAnalyze = async () => {
    if (!productName.trim() || !description.trim()) return
    setLoading(true)
    try {
      const res = await api.analyzeProduct({
        product_name: productName,
        description,
        category,
        target_audience: targetAudience,
      })
      setAnalysis(res)
      if (res.image_prompts?.length > 0) {
        setSelectedPreset(res.image_prompts[0].id)
        setEditablePrompt(res.image_prompts[0].prompt)
      }
      if (res.video_prompt) {
        setVideoPrompt(res.video_prompt)
      }
      setStep('analyzed')
    } catch (err) {
      console.error('Analyze failed:', err)
      alert('วิเคราะห์สินค้าล้มเหลว ลองใหม่อีกครั้ง')
    } finally {
      setLoading(false)
    }
  }

  // Preset change
  const handlePresetChange = (presetId: string) => {
    setSelectedPreset(presetId)
    const preset = analysis?.image_prompts?.find((p) => p.id === presetId)
    if (preset) setEditablePrompt(preset.prompt)
  }

  // Generate images
  const handleGenerateImages = async () => {
    if (!editablePrompt.trim()) return
    setGenLoading(true)
    try {
      const res = await api.generateImage({
        prompt: editablePrompt,
        product_name: productName,
        product_desc: description,
      })
      const newImages: string[] = []
      if (res.image_url) {
        newImages.push(res.image_url)
      } else if (res.images) {
        newImages.push(...res.images)
      }
      if (newImages.length > 0) {
        setGeneratedImages((prev) => [...prev, ...newImages])
        try {
          const saved = JSON.parse(localStorage.getItem('i2m_image_history') || '[]')
          newImages.forEach((url) => saved.unshift({ url, prompt: editablePrompt, created_at: new Date().toISOString(), product_name: productName }))
          localStorage.setItem('i2m_image_history', JSON.stringify(saved.slice(0, 100)))
        } catch {}
      }
      setStep('images_ready')
    } catch (err) {
      console.error('Image gen failed:', err)
      alert('สร้างรูปไม่สำเร็จ')
    } finally {
      setGenLoading(false)
    }
  }

  // Generate video
  const handleGenerateVideo = async () => {
    if (!videoPrompt.trim()) return
    setVideoLoading(true)
    setVideoStatus('กำลังส่งงาน...')
    try {
      const res = await api.generateVideo({
        prompt: videoPrompt,
        provider: 'wavespeed',
        duration: 8,
        aspectRatio: '9:16',
      })
      setVideoTaskId(res.task_id)
      setVideoStatus('อยู่ในคิว...')

      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await api.getVideoStatus(res.task_id)
          if (statusRes.status === 'completed') {
            clearInterval(pollInterval)
            setVideoStatus('เสร็จแล้ว!')
            // Try to extract the actual video URL from the result
            try {
              const innerResult = JSON.parse(statusRes.result?.replace(/'/g, '"') || '{}')
              if (innerResult.task_id) {
                // Try checking the actual WaveSpeed task
                const wsStatus = await api.getVideoStatus(innerResult.task_id)
                if (wsStatus.video_url) {
                  setVideoUrl(wsStatus.video_url)
                }
              }
            } catch { /* ignore */ }
            setVideoLoading(false)
          } else if (statusRes.status === 'failed') {
            clearInterval(pollInterval)
            setVideoStatus('ล้มเหลว')
            setVideoLoading(false)
          } else {
            setVideoStatus('กำลังสร้างวีดีโอ...')
          }
        } catch { /* ignore */ }
      }, 5000)
    } catch (err) {
      console.error('Video gen failed:', err)
      setVideoStatus('เกิดข้อผิดพลาด')
      setVideoLoading(false)
    }
  }

  // Get current preset details
  const currentPreset = analysis?.image_prompts?.find((p) => p.id === selectedPreset)

  return (
    <div className="min-h-[calc(100vh-56px)] bg-white">
      <div className="max-w-4xl mx-auto px-4 py-6">

        {/* ── Header ── */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-gray-900">Product Studio</h1>
          <p className="text-sm text-gray-500 mt-1">สร้างคอนเทนต์สินค้าสำหรับ TikTok</p>
        </div>

        {/* ── Step Progress ── */}
        <div className="flex items-center gap-2 mb-8 text-sm">
          {(['input', 'analyzed', 'images_ready', 'video_ready'] as const).map((s, i) => {
            const stepIndex = ['input', 'analyzed', 'images_ready', 'video_ready'].indexOf(step)
            const isActive = stepIndex >= i
            return (
              <div key={s} className="flex items-center gap-2">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium
                  ${isActive ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-400'}`}>
                  {isActive ? '✓' : i + 1}
                </div>
                <span className={`${isActive ? 'text-gray-900 font-medium' : 'text-gray-400'}`}>
                  {['สินค้า', 'AI วิเคราะห์', 'รูปภาพ', 'วีดีโอ'][i]}
                </span>
                {i < 3 && <div className={`w-8 h-px ${isActive ? 'bg-blue-600' : 'bg-gray-200'}`} />}
              </div>
            )
          })}
        </div>

        {/* ── Product Input Section ── */}
        <div className="bg-white border border-gray-200 rounded-2xl p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">ข้อมูลสินค้า</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Left: Image Upload */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">รูปสินค้า</label>
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-gray-300 rounded-xl h-48 flex items-center justify-center cursor-pointer hover:border-blue-400 transition-colors bg-gray-50"
              >
                {productImage ? (
                  <img src={productImage} alt="Product" className="h-full w-full object-contain p-2" />
                ) : (
                  <div className="text-center text-gray-400">
                    <svg className="w-10 h-10 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <span className="text-sm">แตะเพื่ออัปโหลดรูป</span>
                  </div>
                )}
              </div>
              <input ref={fileInputRef} type="file" accept="image/*" onChange={handleImageUpload} className="hidden" />
            </div>

            {/* Right: Product Details */}
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">ชื่อสินค้า *</label>
                <input
                  type="text"
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  placeholder="เช่น Wireless Earbuds Pro"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">รายละเอียดสินค้า *</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-none"
                  placeholder="รายละเอียดสินค้า จุดเด่น คุณสมบัติ"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">หมวดหมู่</label>
                  <input
                    type="text"
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    placeholder="เช่น อิเล็กทรอนิกส์"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">กลุ่มเป้าหมาย</label>
                  <input
                    type="text"
                    value={targetAudience}
                    onChange={(e) => setTargetAudience(e.target.value)}
                    className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    placeholder="เช่น วัยทำงาน 25-40"
                  />
                </div>
              </div>
              <button
                onClick={handleAnalyze}
                disabled={loading || !productName.trim() || !description.trim()}
                className="w-full py-2.5 bg-blue-600 text-white rounded-xl font-medium text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? 'กำลังวิเคราะห์...' : 'วิเคราะห์สินค้า'}
              </button>
            </div>
          </div>
        </div>

        {/* ── AI Analysis Section ── */}
        {step !== 'input' && analysis && (
          <>
            {/* Hook Suggestions */}
            <div className="bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-100 rounded-2xl p-5 mb-6">
              <h3 className="text-sm font-semibold text-purple-800 mb-3">💡 Hook Suggestions</h3>
              <div className="flex flex-wrap gap-2">
                {analysis.hook_suggestions?.map((hook, i) => (
                  <span key={i} className="bg-white px-3 py-1.5 rounded-full text-sm text-gray-700 border border-purple-200">
                    {hook}
                  </span>
                ))}
              </div>
              {analysis.marketing_copy && (
                <>
                  <h3 className="text-sm font-semibold text-purple-800 mt-4 mb-2">📝 Caption</h3>
                  <p className="text-sm text-gray-600 bg-white rounded-xl p-3 border border-purple-100">{analysis.marketing_copy}</p>
                </>
              )}
              {analysis.hashtags && analysis.hashtags.length > 0 && (
                <>
                  <h3 className="text-sm font-semibold text-purple-800 mt-3 mb-2"># Hashtags</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {analysis.hashtags.map((tag, i) => (
                      <span key={i} className="text-sm text-blue-600">#{tag.replace('#', '')}</span>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* ── Step 1: Image Generation ── */}
            <div className="bg-white border border-gray-200 rounded-2xl p-6 mb-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-1">📸 สร้างรูปภาพ</h2>
              <p className="text-sm text-gray-500 mb-4">เลือกรูปแบบรูปที่ต้องการ แล้วกดสร้าง</p>

              {/* Preset Selector */}
              <div className="flex flex-wrap gap-2 mb-4">
                {analysis.image_prompts?.map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => handlePresetChange(preset.id)}
                    className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors
                      ${selectedPreset === preset.id
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                  >
                    {preset.name}
                  </button>
                ))}
              </div>

              {/* Editable Prompt */}
              <textarea
                value={editablePrompt}
                onChange={(e) => setEditablePrompt(e.target.value)}
                rows={3}
                className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-none mb-4"
              />

              <div className="flex items-center gap-3">
                <button
                  onClick={handleGenerateImages}
                  disabled={genLoading || !editablePrompt.trim()}
                  className="px-6 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-xl font-medium text-sm hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                >
                  {genLoading ? 'กำลังสร้างรูป...' : '✨ สร้างรูป'}
                </button>
                <span className="text-xs text-gray-400">Fal.ai — $0.028/รูป</span>
              </div>

              {/* Generated Images */}
              {generatedImages.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-3">รูปที่สร้างแล้ว:</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {generatedImages.map((imgUrl, i) => (
                      <div key={i} className="relative group rounded-xl overflow-hidden border border-gray-200">
                        <img src={imgUrl} alt={`Generated ${i + 1}`} className="w-full aspect-square object-cover" />
                        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100">
                          <button
                            onClick={() => setSelectedImage(imgUrl)}
                            className={`px-2 py-1 text-xs rounded-lg font-medium transition-colors
                              ${selectedImage === imgUrl ? 'bg-blue-600 text-white' : 'bg-white text-gray-800'}`}
                          >
                            เลือก
                          </button>
                        </div>
                        {selectedImage === imgUrl && (
                          <div className="absolute top-1 left-1 bg-blue-600 text-white text-xs px-2 py-0.5 rounded-md">
                            เลือกแล้ว
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* ── Step 2: Video Generation ── */}
            <div className="bg-white border border-gray-200 rounded-2xl p-6 mb-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-1">🎬 สร้างวีดีโอ</h2>
              <p className="text-sm text-gray-500 mb-4">AI สร้าง Video Prompt ให้อัตโนมัติ แก้ไขได้ตามต้องการ</p>

              {/* AI Video Prompt */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Video Prompt</label>
                <textarea
                  value={videoPrompt}
                  onChange={(e) => setVideoPrompt(e.target.value)}
                  rows={4}
                  className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-none"
                />
              </div>

              {/* Select Image */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">เลือกรูปอ้างอิง (image-to-video)</label>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => setSelectedImage(null)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-colors
                      ${!selectedImage ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}
                  >
                    Text-to-Video (ไม่มีรูป)
                  </button>
                  {generatedImages.map((img, i) => (
                    <button
                      key={i}
                      onClick={() => setSelectedImage(img)}
                      className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-colors
                        ${selectedImage === img ? 'ring-2 ring-blue-500 bg-blue-50 text-blue-700' : 'bg-gray-100 text-gray-600'}`}
                    >
                      รูปที่ {i + 1}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={handleGenerateVideo}
                  disabled={videoLoading || !videoPrompt.trim()}
                  className="px-6 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-medium text-sm hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                >
                  {videoLoading ? 'กำลังสร้างวีดีโอ...' : '🎥 สร้างวีดีโอ'}
                </button>
                <span className="text-xs text-gray-400">WaveSpeed — ~$0.05/วีดีโอ</span>
                {videoStatus && <span className="text-sm text-gray-500">{videoStatus}</span>}
              </div>

              {/* Video Result */}
              {videoUrl && (
                <div className="mt-4">
                  <video src={videoUrl} controls className="w-full max-w-sm rounded-xl border border-gray-200" />
                </div>
              )}
            </div>
          </>
        )}

      </div>
    </div>
  )
}
