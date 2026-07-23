#!/usr/bin/env bash
# ──────────────────────────────────────────────
# UGC CLI — Generate UGC videos from terminal
# Usage: ugc [command] [options]
# ──────────────────────────────────────────────
set -euo pipefail

TUS_HOST="${TUS_HOST:-http://localhost:8105}"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

die()  { echo -e "${RED}✖${NC} $*" >&2; exit 1; }
info() { echo -e "${CYAN}→${NC} $*"; }
ok()   { echo -e "${GREEN}✔${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }

CMD="${1:-}"; shift 2>/dev/null || true

# ── health ────────────────────────────────────
health() {
  local res
  res=$(curl -sf "${TUS_HOST}/health" 2>/dev/null) || die "TUS ไม่ตอบสนองที่ $TUS_HOST"
  echo "$res" | python3 -m json.tool 2>/dev/null || echo "$res"
}

# ── create ────────────────────────────────────
create() {
  local title="" image="" style="holding" duration="15" aspect="9:16" hook="" vp="" cta="" wait=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -t|--title)    title="$2";  shift 2 ;;
      -i|--image)    image="$2";  shift 2 ;;
      -s|--style)    style="$2";  shift 2 ;;
      -d|--duration) duration="$2"; shift 2 ;;
      -a|--aspect)   aspect="$2"; shift 2 ;;
      --hook)        hook="$2";   shift 2 ;;
      --value)       vp="$2";     shift 2 ;;
      --cta)         cta="$2";    shift 2 ;;
      -w|--wait)     wait="1";    shift ;;
      -h|--help)     create_help; return ;;
      *)             die "Unknown: $1" ;;
    esac
  done
  [[ -z "$title" && -z "$image" ]] && die "ต้อง --title หรือ --image"
  local body
  body=$(python3 -c "
import json
d = {'product_title':'$title','product_image':'$image','ugc_style':'$style','duration':$duration,'aspect_ratio':'$aspect'}
if '$hook': d['hook']='$hook'
if '$vp':   d['value_proposition']='$vp'
if '$cta':  d['cta']='$cta'
print(json.dumps(d))
")
  info "POST ${TUS_HOST}/pipeline/run"
  info "  style=${style} duration=${duration}s aspect=${aspect}"
  local res job_id
  res=$(curl -s -X POST "${TUS_HOST}/pipeline/run" -H "Content-Type: application/json" -d "$body") || die "ส่ง request ไม่สำเร็จ"
  job_id=$(echo "$res" | python3 -c "import sys,json; print(json.load(sys.stdin).get('job_id',''))" 2>/dev/null || echo "")
  [[ -z "$job_id" ]] && { echo "$res" | python3 -m json.tool 2>/dev/null || echo "$res"; return; }
  ok "Job ID: ${BOLD}${job_id}${NC}"
  echo -e "    ดูสถานะ: ${CYAN}ugc status $job_id${NC}"
  echo -e "    ทั้งหมด:  ${CYAN}ugc list${NC}"
  [[ -n "$wait" ]] && { echo ""; poll_job "$job_id"; }
}

create_help() {
  echo "ใช้: ugc create [options]"
  echo "  -t, --title TEXT     ชื่อสินค้า"
  echo "  -i, --image URL      URL รูปสินค้า"
  echo "  -s, --style TYPE     holding|usage|review|talking|unbox (default: holding)"
  echo "  -d, --duration SEC   (default: 15)"
  echo "  -a, --aspect RATIO   (default: 9:16)"
  echo "      --hook TEXT      ข้อความ Hook"
  echo "      --value TEXT     Value proposition"
  echo "      --cta TEXT       Call-to-action"
  echo "  -w, --wait           รอจนเสร็จ"
}

# ── status ────────────────────────────────────
status() {
  [[ -z "${1:-}" ]] && die "ใช้: ugc status <job_id>"
  local res
  res=$(curl -sf "${TUS_HOST}/pipeline/$1/status" 2>/dev/null) || die "job $1 ไม่พบ"
  render_job "$res"
}

# ── list ──────────────────────────────────────
list_jobs() {
  local limit="${1:-20}"
  local res
  res=$(curl -sf "${TUS_HOST}/pipeline/list?limit=$limit" 2>/dev/null) || die "ดึงรายการ jobs ไม่ได้"
  echo ""
  echo -e "${BOLD}📋 Pipeline Jobs (ล่าสุด ${limit})${NC}"
  echo "──────────────────────────────────────────────────────────"
  echo "$res" | python3 -c "
import sys, json
data = json.load(sys.stdin)
jobs = data if isinstance(data, list) else data.get('jobs', data.get('data', []))
for j in jobs:
    jid = j.get('job_id', j.get('id', '?'))
    st = j.get('status', '?')
    title = j.get('product_title', j.get('title', ''))[:50]
    cost = j.get('cost_estimate', j.get('cost', ''))
    print(f'  {jid:<20} {st:<12} {title}')
    if cost: print(f'  {\"\":<20} 💰 {cost}')
" 2>/dev/null || echo "$res" | python3 -m json.tool
}

# ── poll ──────────────────────────────────────
poll_job() {
  local job_id="$1" status="" dot
  echo -ne "  รอ pipeline."
  while true; do
    status=$(curl -sf "${TUS_HOST}/pipeline/$job_id/status" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
    case "$status" in
      completed)          echo ""; ok "✅ เสร็จ!"; render_job "$(curl -sf "${TUS_HOST}/pipeline/$job_id/status" 2>/dev/null)"; return 0 ;;
      completed_with_errors) echo ""; warn "⚠️ เสร็จ但有 error"; render_job "$(curl -sf "${TUS_HOST}/pipeline/$job_id/status" 2>/dev/null)"; return 0 ;;
      failed)             echo ""; warn "❌ ล้มเหลว"; curl -sf "${TUS_HOST}/pipeline/$job_id/status" 2>/dev/null | python3 -m json.tool; return 1 ;;
      running|pending|processing|queued|waiting) echo -n "." ;;
      *)                  echo ""; warn "ไม่รู้จักสถานะ: $status"; curl -sf "${TUS_HOST}/pipeline/$job_id/status" 2>/dev/null | python3 -m json.tool; return 1 ;;
    esac
    sleep 5
  done
}

render_job() {
  echo ""
  echo "$1" | python3 -c "
import sys, json
j = json.load(sys.stdin)
print(f'  📌 Job ID:    {j.get(\"job_id\",j.get(\"id\",\"?\"))}')
print(f'  📊 สถานะ:     {j.get(\"status\",\"?\")}')
print(f'  📦 สินค้า:    {j.get(\"product_title\",j.get(\"title\",\"?\"))}')
print(f'  🎬 สไตล์:     {j.get(\"ugc_style\",\"?\")}')
print(f'  ⏱  ระยะเวลา:   {j.get(\"duration\",\"?\")}s')
print(f'  💰 ค่าใช้จ่าย: {j.get(\"cost_estimate\",j.get(\"cost\",\"?\"))}')
if j.get('video_url'): print(f'  🎥 ไฟล์:       {j[\"video_url\"]}')
steps = j.get('steps',{})
if steps:
    for k,v in steps.items():
        print(f'  ├─ {k}: {v.get(\"status\",\"?\")}')
print('')
" 2>/dev/null || echo "$1" | python3 -m json.tool 2>/dev/null || true
  echo ""
}

# ── cancel / replay (ไม่ support) ─────────────
cancel() { warn "TUS ไม่มี endpoint ยกเลิก job";   echo "  รอให้จบหรือ restart service"; }
replay() { warn "TUS ไม่มี endpoint replay job"; echo "  ใช้: ugc create ด้วย参数เดิม"; }

# ── config ────────────────────────────────────
show_config() {
  echo -e "${BOLD}⚙️  Config${NC}"
  echo "  TUS_HOST: ${TUS_HOST}"
  echo "  เปลี่ยน: export TUS_HOST=http://localhost:8105"
  echo "          export TUS_HOST=https://m2igen.com/api/tiktok/ugc"
}

# ── help ──────────────────────────────────────
show_help() {
  echo -e "${BOLD}UGC CLI${NC} — สร้างวิดีโอ UGC จาก terminal"
  echo ""
  echo "  ${CYAN}ugc health${NC}           เช็ค service"
  echo "  ${CYAN}ugc create${NC}           สร้างวิดีโอใหม่"
  echo "  ${CYAN}ugc status <id>${NC}      ดูสถานะ job"
  echo "  ${CYAN}ugc list [N]${NC}         รายการ jobs (default 20)"
  echo "  ${CYAN}ugc cancel <id>${NC}      ยกเลิก job"
  echo "  ${CYAN}ugc replay <id>${NC}      รันซ้ำ"
  echo "  ${CYAN}ugc config${NC}           ดู config"
  echo ""
  echo "ตัวอย่าง:"
  echo "  ugc create -t 'Tea Tree Toner' -i 'https://...' -s holding -d 15"
  echo "  ugc create -t 'Lip Oil' --hook 'ปากสวยใน 3 วิ' --wait"
  echo "  ugc status vid_e06f76da"
}

# ── main ──────────────────────────────────────
case "$CMD" in
  health|ping)    health ;;
  status)         status "${1:-}" ;;
  list)           list_jobs "${1:-20}" ;;
  create|new)     create "$@" ;;
  cancel|rm)      cancel "${1:-}" ;;
  replay|retry)   replay "${1:-}" ;;
  config)         show_config ;;
  --help|-h|help|"") show_help ;;
  *) die "ไม่รู้จัก '$CMD' — ใช้ ugc help" ;;
esac
