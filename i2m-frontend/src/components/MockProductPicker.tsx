import { useState } from 'react'
import { mockProducts, type MockProduct } from '../data/mockProducts'

interface Props {
  onSelect: (product: MockProduct) => void
  onClose: () => void
}

const categoryColors: Record<string, string> = {
  Electronics: 'from-blue-500/10 to-indigo-500/10 text-blue-600 border-blue-200',
  Beauty: 'from-pink-500/10 to-rose-500/10 text-pink-600 border-pink-200',
  Fashion: 'from-amber-500/10 to-orange-500/10 text-amber-600 border-amber-200',
}

export default function MockProductPicker({ onSelect, onClose }: Props) {
  const [selected, setSelected] = useState<MockProduct | null>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  return (
    <div className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      {/* Panel */}
      <div className="relative w-full max-w-2xl max-h-[85vh] bg-white dark:bg-slate-800 rounded-t-3xl sm:rounded-3xl shadow-2xl overflow-hidden flex flex-col animate-slide-up">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-slate-100 dark:border-slate-700">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <span className="text-2xl">✨</span> Demo Products
              </h2>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">เลือกสินค้าตัวอย่างเพื่อทดลองใช้งาน</p>
            </div>
            <button
              onClick={onClose}
              className="w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors"
            >
              <span className="material-symbols-outlined text-xl">close</span>
            </button>
          </div>
        </div>

        {/* Product Grid */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {mockProducts.map((product) => {
              const isSelected = selected?.id === product.id
              const isHovered = hoveredId === product.id
              const colorClass = categoryColors[product.category] || categoryColors.Electronics

              return (
                <button
                  key={product.id}
                  onClick={() => setSelected(product)}
                  onMouseEnter={() => setHoveredId(product.id)}
                  onMouseLeave={() => setHoveredId(null)}
                  className={`relative flex flex-col rounded-2xl overflow-hidden border-2 transition-all duration-200 text-left ${
                    isSelected
                      ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-900/20 shadow-lg shadow-indigo-500/10 ring-2 ring-indigo-500/20'
                      : isHovered
                        ? 'border-slate-300 dark:border-slate-600 shadow-md'
                        : 'border-slate-100 dark:border-slate-700 shadow-sm hover:shadow-md'
                  }`}
                >
                  {/* Image */}
                  <div className="relative aspect-square overflow-hidden bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-700 dark:to-slate-800">
                    <img
                      src={product.imageUrl}
                      alt={product.name}
                      className="w-full h-full object-cover transition-transform duration-300 hover:scale-105"
                      loading="lazy"
                    />
                    {/* Category Badge */}
                    <span className={`absolute top-2 left-2 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gradient-to-r ${colorClass} border backdrop-blur-sm`}>
                      {product.category}
                    </span>
                    {/* Price Badge */}
                    <span className="absolute top-2 right-2 px-2 py-0.5 rounded-full text-[11px] font-bold bg-white/90 dark:bg-slate-800/90 text-slate-900 dark:text-white backdrop-blur-sm shadow-sm">
                      {product.price}
                    </span>
                    {/* Selected Check */}
                    {isSelected && (
                      <div className="absolute inset-0 bg-indigo-500/10 flex items-center justify-center">
                        <div className="w-12 h-12 rounded-full bg-indigo-500 flex items-center justify-center shadow-lg animate-bounce-in">
                          <span className="material-symbols-outlined text-white text-2xl">check</span>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="p-3 flex flex-col gap-1.5">
                    <h3 className="text-sm font-semibold text-slate-900 dark:text-white line-clamp-1">
                      {product.name}
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed">
                      {product.description}
                    </p>
                    {/* Feature Pills */}
                    <div className="flex flex-wrap gap-1 mt-1">
                      {product.features.slice(0, 3).map((f) => (
                        <span
                          key={f}
                          className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300"
                        >
                          {f}
                        </span>
                      ))}
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-100 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-800/80 backdrop-blur-sm">
          <button
            onClick={() => selected && onSelect(selected)}
            disabled={!selected}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-500 text-white font-semibold text-sm flex items-center justify-center gap-2 shadow-lg shadow-indigo-500/25 transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-xl hover:shadow-indigo-500/30 active:scale-[0.98]"
          >
            <span className="material-symbols-outlined text-lg">auto_awesome</span>
            {selected ? `ใช้ ${selected.name}` : 'เลือกสินค้าเพื่อเริ่มต้น'}
          </button>
        </div>
      </div>
    </div>
  )
}
