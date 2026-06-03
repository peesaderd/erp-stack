import { useState, useEffect } from 'react'

interface ImageItem {
  url: string
  prompt: string
  created_at: string
  product_name?: string
}

export default function ImageGallery() {
  const [images, setImages] = useState<ImageItem[]>([])
  const [loading, setLoading] = useState(true)
  const [previewImg, setPreviewImg] = useState<string | null>(null)

  useEffect(() => {
    try {
      const saved = localStorage.getItem('i2m_image_history')
      if (saved) {
        setImages(JSON.parse(saved))
      }
    } catch { /* ignore */ }
    setLoading(false)
  }, [])

  const clearHistory = () => {
    localStorage.removeItem('i2m_image_history')
    setImages([])
  }

  return (
    <div className="min-h-[calc(100vh-56px)] bg-white">
      <div className="max-w-4xl mx-auto px-4 py-6">

        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Image Gallery</h1>
            <p className="text-sm text-gray-500 mt-1">รูปที่สร้างไว้แล้ว</p>
          </div>
          {images.length > 0 && (
            <button onClick={clearHistory} className="text-sm text-red-500 hover:text-red-600">
              ล้างประวัติ
            </button>
          )}
        </div>

        {loading ? (
          <div className="text-center py-12 text-gray-400">กำลังโหลด...</div>
        ) : images.length === 0 ? (
          <div className="text-center py-16">
            <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <p className="text-gray-400 text-sm mb-2">ยังไม่มีรูป</p>
            <p className="text-gray-400 text-xs">ไปที่ Product Studio เพื่อสร้างรูปแรก</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {images.map((img, i) => (
                <div key={i} className="relative group rounded-xl overflow-hidden border border-gray-200 bg-gray-50">
                  <img
                    src={img.url}
                    alt={`Generated ${i + 1}`}
                    className="w-full aspect-square object-cover cursor-pointer"
                    onClick={() => setPreviewImg(img.url)}
                  />
                  <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <p className="text-xs text-white truncate">{img.prompt?.slice(0, 60)}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Preview Modal */}
            {previewImg && (
              <div
                className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
                onClick={() => setPreviewImg(null)}
              >
                <img src={previewImg} alt="Preview" className="max-w-full max-h-full rounded-2xl" />
                <button
                  className="absolute top-4 right-4 text-white text-xl"
                  onClick={() => setPreviewImg(null)}
                >
                  ✕
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
