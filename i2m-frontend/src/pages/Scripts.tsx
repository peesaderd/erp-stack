import { useState } from 'react'
import { api } from '../lib/api'

export default function Scripts() {
  const [mode, setMode] = useState<'ugc' | 'review' | 'affiliate'>('ugc')
  const [productName, setProductName] = useState('')
  const [productDesc, setProductDesc] = useState('')
  const [scriptStyle, setScriptStyle] = useState('holding_product')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)

  const handleGenerate = async () => {
    if (!productName.trim()) return
    setLoading(true)
    setResult('')
    try {
      const data = await (mode === 'ugc'
        ? api.generateUgcScript({ productName, productDesc, style: scriptStyle })
        : api.generateReviewScript({ productName, productDesc }))
      setResult(data.script || data.content || JSON.stringify(data, null, 2))
    } catch (e: any) {
      setResult(`Error: ${e.message}`)
    }
    setLoading(false)
  }

  return (
    <div className="space-y-6 pb-8">
      <div className="py-4">
        <h1 className="title-ios-2">Script Generator</h1>
        <p className="subhead-ios mt-1">Create TikTok UGC scripts in seconds</p>
      </div>

      <div className="segmented-ios max-w-sm">
        {(['ugc', 'review', 'affiliate'] as const).map((m) => (
          <button key={m} className={mode === m ? 'active' : ''} onClick={() => setMode(m)}>
            {m === 'ugc' ? 'UGC' : m === 'review' ? 'Review' : 'Affiliate'}
          </button>
        ))}
      </div>

      <div className="card-ios p-5 space-y-4">
        <div>
          <label className="subhead-ios font-medium mb-1 block">Product Name</label>
          <input className="search-ios" placeholder="e.g. Wireless Earbuds Pro" value={productName} onChange={(e) => setProductName(e.target.value)} />
        </div>
        <div>
          <label className="subhead-ios font-medium mb-1 block">Product Description</label>
          <textarea className="search-ios min-h-[100px] resize-none" placeholder="Describe the product features, target audience..." value={productDesc} onChange={(e) => setProductDesc(e.target.value)} />
        </div>
        {mode === 'ugc' && (
          <div>
            <label className="subhead-ios font-medium mb-1 block">Script Style</label>
            <div className="segmented-ios max-w-sm">
              {['holding_product', 'product_usage', 'ugc_review'].map((s) => (
                <button key={s} className={scriptStyle === s ? 'active' : ''} onClick={() => setScriptStyle(s)}>
                  {s === 'holding_product' ? 'Holding Product' : s === 'product_usage' ? 'Product Usage' : 'UGC Review'}
                </button>
              ))}
            </div>
          </div>
        )}
        <button onClick={handleGenerate} disabled={loading || !productName.trim()}
          className="btn-ios w-full py-3 bg-[var(--color-system-blue)] text-white font-semibold text-[17px] disabled:opacity-50">
          {loading ? 'Generating...' : 'Generate Script'}
        </button>
      </div>

      {result && (
        <div className="card-ios p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="title-ios-3">Result</h3>
            <button onClick={() => navigator.clipboard.writeText(result)} className="btn-ios text-[var(--color-system-blue)] font-medium text-[15px]">Copy</button>
          </div>
          <pre className="text-[15px] whitespace-pre-wrap font-sans text-[var(--color-secondary-label)] leading-relaxed">{result}</pre>
        </div>
      )}
    </div>
  )
}
