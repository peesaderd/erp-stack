const UGC_API = '/api/i2m/ugc'
const ETZY_API = '/api/i2m/etsy-img'

export const api = {
  // ── Product Analyze (via Mistral Agent) ──
  analyzeProduct: async (file: File, productName: string, productDesc?: string) => {
    const formData = new FormData()
    formData.append('product_name', productName)
    formData.append('description', productDesc || '')
    formData.append('file', file)
    const res = await fetch(`${UGC_API}/product/analyze`, {
      method: 'POST',
      body: formData,
    })
    if (!res.ok) {
      const err = await res.text().catch(() => '')
      throw new Error(`Analysis failed (${res.status}): ${err}`)
    }
    return res.json()
  },

  // ── Image Generation (Fal.ai via Etsy Wizard) ──
  generateImage: async (prompt: string, productName?: string, productDesc?: string, style?: string, aspectRatio?: string) => {
    const res = await fetch(`${ETZY_API}/ai/generate-image`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        product_name: productName || '',
        description: productDesc || '',
        style: style || '',
        prompt,
        ...(aspectRatio ? { aspect_ratio: aspectRatio } : {}),
      }),
    })
    if (!res.ok) {
      const err = await res.text().catch(() => '')
      throw new Error(`Image gen failed (${res.status}): ${err}`)
    }
    const data = await res.json()
    return { url: data.image_url || data.url }
  },

  // ── Video Generation (WaveSpeed - async queue) ──
  generateVideo: async (prompt: string, imageUrl?: string, productName?: string) => {
    const res = await fetch(`${UGC_API}/video/queue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        ...(imageUrl ? { image_url: imageUrl } : {}),
        ...(productName ? { product_name: productName } : {}),
      }),
    })
    if (!res.ok) {
      const err = await res.text().catch(() => '')
      throw new Error(`Video queue failed (${res.status}): ${err}`)
    }
    const data = await res.json()
    return { task_id: data.task_id || data.id }
  },

  // ── Video Status ──
  getVideoResult: async (taskId: string) => {
    const res = await fetch(`${UGC_API}/video/queue-status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: taskId }),
    })
    if (!res.ok) throw new Error(`Status check failed (${res.status})`)
    const data = await res.json()
    return { status: data.status, url: data.url || data.video_url }
  },

  // ── UGC Scripts ──
  generateUgcScript: async (data: {
    productName: string
    productDesc: string
    style?: string
  }) =>
    (await fetch(`${UGC_API}/scripts/ugc`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        product_name: data.productName,
        product_desc: data.productDesc,
        ...(data.style ? { style: data.style } : {}),
      }),
    })).json(),

  generateReviewScript: async (data: {
    productName: string
    productDesc: string
  }) =>
    (await fetch(`${UGC_API}/scripts/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        product_name: data.productName,
        customer_problem: data.productDesc,
      }),
    })).json(),

  generateScript: async (data: {
    productName: string
    productDesc: string
  }) =>
    (await fetch(`${UGC_API}/scripts/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        product_name: data.productName,
        product_desc: data.productDesc,
      }),
    })).json(),

  getTemplates: async () =>
    (await fetch(`${UGC_API}/scripts/templates`)).json(),

  getVideoProviders: async () =>
    (await fetch(`${UGC_API}/video/providers`)).json(),

  // ── Export to Channel ──
  exportToChannel: async (url: string, type: string, prompt: string) => {
    const res = await fetch(`${UGC_API}/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, type, prompt }),
    })
    return res.json()
  },
}

export default api
