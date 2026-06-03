import { useState } from 'react'
import { api } from '../lib/api'

export default function ImageGen() {
  const [prompt, setPrompt] = useState('')
  const [style, setStyle] = useState('realistic')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)

  const styles = [
    { id: 'realistic', label: 'Realistic' },
    { id: 'product', label: 'Product' },
    { id: 'cartoon', label: 'Cartoon' },
    { id: 'minimal', label: 'Minimal' },
  ]

  const handleGenerate = async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setResult(null)
    setImageUrl(null)
    try {
      const data = await api.image.generateEtsy({ prompt, style })
      const url = data.url || data.image_url || data.image
      if (url) setImageUrl(url)
      else setResult(JSON.stringify(data, null, 2))
    } catch (e: any) {
      setResult(`Error: ${e.message}`)
    }
    setLoading(false)
  }

  return (
    <div className="space-y-6 pb-8">
      <div className="py-4">
        <h1 className="title-ios-2">Image Generator</h1>
        <p className="subhead-ios mt-1">AI-powered product & marketing images</p>
      </div>

      <div>
        <h3 className="subhead-ios font-medium mb-2">Style</h3>
        <div className="segmented-ios max-w-sm">
          {styles.map((s) => (
            <button key={s.id} className={style === s.id ? 'active' : ''} onClick={() => setStyle(s.id)}>{s.label}</button>
          ))}
        </div>
      </div>

      <div className="card-ios p-5 space-y-4">
        <div>
          <label className="subhead-ios font-medium mb-1 block">Image Prompt</label>
          <textarea className="search-ios min-h-[100px] resize-none"
            placeholder="Describe the image..." value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        </div>
        <button onClick={handleGenerate} disabled={loading || !prompt.trim()}
          className="btn-ios w-full py-3 bg-[var(--color-system-blue)] text-white font-semibold text-[17px] disabled:opacity-50">
          {loading ? 'Generating...' : 'Generate Image'}
        </button>
      </div>

      {loading && (
        <div className="card-ios p-4">
          <div className="subhead-ios font-medium">Generating your image...</div>
          <div className="progress-ios mt-3"><div className="progress-ios-bar w-1/2" /></div>
        </div>
      )}

      {imageUrl && (
        <div className="card-ios overflow-hidden">
          <img src={imageUrl} alt="Generated" className="w-full object-cover" />
          <div className="p-3 flex justify-between items-center">
            <span className="footnote-ios">Generated Image</span>
            <a href={imageUrl} target="_blank" rel="noopener noreferrer" className="btn-ios text-[var(--color-system-blue)] font-medium text-[15px]">Open Full Size</a>
          </div>
        </div>
      )}

      {result && !imageUrl && (
        <div className="card-ios p-5">
          <pre className="text-[13px] whitespace-pre-wrap font-mono text-[var(--color-secondary-label)]">{result}</pre>
        </div>
      )}
    </div>
  )
}
