const UGC_API = '/api/i2m/ugc'
const ETZY_API = '/api/i2m/etsy-img'

export const api = {
  // ── Product Analyze (via Gemini) ──
  analyzeProduct: async (data: {
    product_name: string
    description: string
    category?: string
    target_audience?: string
    image_url?: string
  }) =>
    (await fetch(`${UGC_API}/product/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })).json(),

  // ── Image Generation (Fal.ai via Etsy Wizard) ──
  generateImage: async (data: {
    prompt: string
    product_name?: string
    product_desc?: string
    style?: string
  }) =>
    (await fetch(`${ETZY_API}/ai/generate-image`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        product_name: data.product_name || '',
        ...(data.product_desc ? { description: data.product_desc } : {}),
        ...(data.style ? { style: data.style } : {}),
        prompt: data.prompt,
      }),
    })).json(),

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

  // ── Video Generation (WaveSpeed) ──
  generateVideo: async (data: {
    prompt: string
    provider?: string
    duration?: number
    aspectRatio?: string
  }) =>
    (await fetch(`${UGC_API}/video/queue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: data.prompt,
        ...(data.provider ? { provider: data.provider } : {}),
        ...(data.duration ? { duration: data.duration } : {}),
        ...(data.aspectRatio ? { aspect_ratio: data.aspectRatio } : {}),
      }),
    })).json(),

  getVideoStatus: async (taskId: string) =>
    (await fetch(`${UGC_API}/video/queue-status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: taskId }),
    })).json(),

  getVideoProviders: async () =>
    (await fetch(`${UGC_API}/video/providers`)).json(),
}
