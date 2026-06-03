const UGC_API = '/api/i2m/ugc'
const ETZY_API = '/api/i2m/etsy-img'

export const api = {
  ugc: {
    generateScript: async (data: { productName: string; productDesc: string }) =>
      (await fetch(`${UGC_API}/scripts/generate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })).json(),
    generateUgcScript: async (data: { productName: string; productDesc: string; style?: string }) =>
      (await fetch(`${UGC_API}/scripts/ugc`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })).json(),
    generateVideo: async (data: { prompt: string; provider?: string; duration?: number; aspectRatio?: string }) =>
      (await fetch(`${UGC_API}/video/generate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })).json(),
    getVideoStatus: async (taskId: string) =>
      (await fetch(`${UGC_API}/video/queue-status`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ task_id: taskId } ) })).json(),
    getProviders: async () =>
      (await fetch(`${UGC_API}/video/providers`)).json(),
    getTemplates: async () =>
      (await fetch(`${UGC_API}/scripts/templates`)).json(),
  },
  image: {
    generateEtsy: async (data: { prompt: string; style?: string; description?: string }) =>
      (await fetch(`${ETZY_API}/ai/generate-image`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ product_name: data.prompt, description: data.description || data.prompt, style: data.style || 'product' }) })).json(),
  },
}
