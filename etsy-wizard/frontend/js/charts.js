/* ─── SVG Chart Helpers ─── */
const Charts = {
  barChart(container, data, {barColor='linear-gradient(180deg, #e45858, #f97316)', height=200, maxValue}={}) {
    const max = maxValue || Math.max(...data.map(d => d.value), 1);
    const cols = data.map(d => {
      const pct = (d.value / max) * 100;
      return `<div class="chart-bar-col"><div class="bar" style="height:${Math.max(pct, 4)}%;background:${barColor}"></div><span class="bar-label">${d.day}</span></div>`;
    }).join('');
    container.innerHTML = `<div class="chart-bar" style="height:${height}px">${cols}</div>`;
  },

  donutChart(container, data, size=160) {
    const total = data.reduce((s, d) => s + d.value, 0);
    const radius = 58;
    const circ = 2 * Math.PI * radius;
    let offset = 0;
    const slices = data.map(d => {
      const pct = d.value / total;
      const dash = pct * circ;
      const slice = `<circle r="${radius}" cx="80" cy="80" fill="none" stroke="${d.color}" stroke-width="22" stroke-dasharray="${dash} ${circ - dash}" stroke-dashoffset="${-offset}" />`;
      offset += dash;
      return slice;
    }).join('');
    
    container.innerHTML = `
      <div class="donut-chart" style="width:${size}px;height:${size}px">
        <svg width="${size}" height="${size}" viewBox="0 0 160 160">${slices}</svg>
        <div class="donut-center"><span class="num">${total}</span><span class="lbl">Total</span></div>
      </div>
      <div class="legend">${data.map(d => `<span class="legend-item"><span class="legend-dot" style="background:${d.color}"></span>${d.label} (${d.value})</span>`).join('')}</div>`;
  },

  statusBadge(status) {
    const colors = { Active: '#22c55e', Shipped: '#22c55e', Paid: '#3b82f6', Draft: '#eab308', Processing: '#a855f7', Expired: '#7f7f8f' };
    const bg = { Active: 'rgba(34,197,94,.12)', Shipped: 'rgba(34,197,94,.12)', Paid: 'rgba(59,130,246,.12)', Draft: 'rgba(234,179,8,.12)', Processing: 'rgba(168,85,247,.12)', Expired: 'rgba(127,127,143,.12)' };
    return `<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:500;background:${bg[status]||bg.Expired};color:${colors[status]||colors.Expired}">${status}</span>`;
  },

  money(amount) { return '$' + Number(amount).toFixed(2); },

  formatNum(n) { return n.toLocaleString(); }
};
