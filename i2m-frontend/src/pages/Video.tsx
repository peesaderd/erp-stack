import { useState } from 'react'
import { api } from '../lib/api'

export default function Video() {
  const [provider, setProvider] = useState('wavespeed')
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [result, setResult] = useState<string | null>(null)

  const providers = [
    { id: 'wavespeed', name: 'WaveSpeed', cost: '$0.05', color: '#007AFF' },
    { id: 'minimax', name: 'Minimax', cost: '$0.10', color: '#34C759' },
    { id: 'kling', name: 'Kling', cost: '$0.60', color: '#FF9500' },
    { id: 'runway', name: 'Runway', cost: '$0.40', color: '#FF3B30' },
  ]

  const handleGenerate = async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setStatus('Generating...')
    setResult(null)
    try {
      const data = await api.ugc.generateVideo({ prompt, provider, duration: 8, aspectRatio: '9:16' })
      if (data.task_id) {
        setStatus(`Task queued: ${data.task_id}`)
      } else if (data.detail) {
        setStatus(`Error: ${data.detail}`)
      }
      setResult(JSON.stringify(data, null, 2))
    } catch (e: any) {
      setStatus(`Error: ${e.message}`)
    }
    setLoading(false)
  }

  return (
    <div className="space-y-6 pb-8">
      <div className="py-4">
        <h1 className="title-ios-2">Video Generator</h1>
        <p className="subhead-ios mt-1">AI video from text prompts</p>
      </div>

      <div>
        <h3 className="subhead-ios font-medium mb-2">Provider</h3>
        <div className="grid grid-cols-2 gap-2">
          {providers.map((p) => (
            <button key={p.id} onClick={() => setProvider(p.id)}
              className={`card-ios p-3 text-left btn-ios ${provider === p.id ? 'ring-2 ring-[var(--color-system-blue)]' : ''}`}>
              <div className="body-ios font-medium">{p.name}</div>
              <div className="footnote-ios">{p.cost}/video</div>
            </button>
          ))}
        </div>
      </div>

      <div className="card-ios p-5 space-y-4">
        <div>
          <label className="subhead-ios font-medium mb-1 block">Video Prompt</label>
          <textarea className="search-ios min-h-[120px] resize-none"
            placeholder="Describe the video you want to generate..."
            value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        </div>
        <button onClick={handleGenerate} disabled={loading || !prompt.trim()}
          className="btn-ios w-full py-3 bg-[var(--color-system-blue)] text-white font-semibold text-[17px] disabled:opacity-50">
          {loading ? 'Generating...' : 'Generate Video'}
        </button>
      </div>

      {status && (
        <div className={`card-ios p-4 ${status.includes('Error') ? 'bg-red-50' : ''}`}>
          <div className="subhead-ios font-medium">{status}</div>
          {loading && <div className="progress-ios mt-3"><div className="progress-ios-bar w-2/3" /></div>}
        </div>
      )}

      {result && (
        <div className="card-ios p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="title-ios-3">Response</h3>
            <button onClick={() => navigator.clipboard.writeText(result!)} className="btn-ios text-[var(--color-system-blue)] font-medium text-[15px]">Copy</button>
          </div>
          <pre className="text-[13px] whitespace-pre-wrap font-mono text-[var(--color-secondary-label)]">{result}</pre>
        </div>
      )}
    </div>
  )
}
