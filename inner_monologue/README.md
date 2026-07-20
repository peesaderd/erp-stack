# Inner Monologue Agent

ระบบให้ AI Agent มี **กระบวนการคิดภายใน (Inner Monologue)** — คิดก่อนทำ ดูผลก่อนคิดต่อ

## สถาปัตยกรรม

```
┌─────────────────────────────────────────────┐
│         Inner Monologue Agent               │
│                                              │
│  ┌───────────────────────────────────────┐  │
│  │  ReAct Loop                           │  │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  │  │
│  │  │ THINK  │→ │  ACT   │→ │OBSERVE │  │  │
│  │  │ (คิด)   │  │ (ทำ)    │  │ (ดูผล)  │  │  │
│  │  └────────┘  └────────┘  └────────┘  │  │
│  │       │                            │  │  │
│  │       └───────────┐────────────────┘  │  │
│  │                   ▼                    │  │
│  │              ┌──────────┐              │  │
│  │              │  DONE?   │              │  │
│  │              └──────────┘              │  │
│  └───────────────────────────────────────┘  │
│                                              │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ Memory   │ │Condenser │ │Self-        │ │
│  │(จำประวัติ)│ │(สรุปความ)│ │Reflection   │ │
│  └──────────┘ └──────────┘ └─────────────┘ │
└─────────────────────────────────────────────┘
```

## วิธีใช้

### ตั้งค่า API Key

```bash
export MISTRAL_API_KEY="laTWa8j4VvEeizOzVcQfwLQF8Vu2ZlOb"
```

### รัน Agent

```bash
# รันจาก root ของ erp-stack
cd /workspace/erp-stack
python -m inner_monologue.main "วิเคราะห์ ERP เราเทียบ Odoo"

# รันแบบไม่แสดงรายละเอียด
python -m inner_monologue.main --quiet "ช่วยเขียน Docs"

# ดูประวัติที่มีอยู่
python -m inner_monologue.main --list-history

# ล้างประวัติ
python -m inner_monologue.main --clear-memory
```

### ใช้ในโค้ด Python

```python
from inner_monologue import InnerMonologueAgent, ConversationMemory, Heartbeat

memory = ConversationMemory(persistence_dir="./.inner-monologue-memory")
heartbeat = Heartbeat()

agent = InnerMonologueAgent(
    llm_config={
        "api_key": "your-mistral-api-key",
        "model": "mistral-large-2411",
    },
    memory=memory,
    heartbeat=heartbeat,
)

result = agent.run("วิเคราะห์โครงสร้างโปรเจค")
print(result)
```

## Components

| Component | ไฟล์ | หน้าที่ |
|-----------|------|--------|
| **Agent** | `agent.py` | ตัวแทนหลัก มี ReAct Loop |
| **Heartbeat** | `heartbeat.py` | แสดงสถานะทุกรอบ |
| **Memory** | `memory.py` | จำประวัติ + Condenser |
| **Self-Reflection** | `self_reflection.py` | เรียนรู้จากผู้ใช้ |
| **HITL** | `hitl.py` | Human-in-the-Loop |

## ตัวอย่าง Output

```
============================================================
  🧠 INNER MONOLOGUE AGENT
  Task: วิเคราะห์ ERP เราเทียบ Odoo
  Started: 14:30:00
============================================================

  [🧠] รอบที่ 1
       ต้องอ่านโครงสร้างโปรเจคก่อน

  [⚡] รอบที่ 1
       terminal: ls -la /workspace/erp-project

  [📊] รอบที่ 1
       พบ: app/, migrations/, requirements.txt

  ...

============================================================
  ✅ งานเสร็จ (ใช้เวลา 45 วินาที)
============================================================
```
