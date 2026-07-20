# Inner Monologue Agent — Architecture

## Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        User / HITL                           │
│            (Human-in-the-Loop via Flag Files)                │
└──────────────────────────┬───────────────────────────────────┘
                           │ task
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    InnerMonologueAgent                        │
│                     (ReAct Loop Core)                        │
│                                                              │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│   │  THINK   │───▶│   ACT    │───▶│ OBSERVE  │──┐           │
│   │ (LLM)    │    │ (LLM)    │    │ (Execute) │  │           │
│   └──────────┘    └──────────┘    └──────────┘  │           │
│       ▲                                         │           │
│       └─────────────────────────────────────────┘           │
│                    (loop until done)                         │
└──────────────────────────────────────────────────────────────┘
           │              │              │              │
           ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Heartbeat   │ │  Memory      │ │ Self-        │ │  HITL        │
│  (Logging)   │ │ (Persistence)│ │ Reflection   │ │ (Flag Files) │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

## Components

### 1. InnerMonologueAgent (`agent.py`)
Core ReAct Loop engine. Orchestrates Think → Act → Observe cycle.

| Method | Role |
|--------|------|
| `run(task)` | Entry point — starts the loop |
| `_loop()` | Main ReAct loop (max 50 rounds) |
| `_think()` | Calls LLM to produce thought JSON |
| `_act()` | Calls LLM to decide action from thought |
| `_observe()` | Executes action (terminal/file/code) |
| `_finalize()` | Writes summary + triggers self-reflection |

### 2. Heartbeat (`heartbeat.py`)
Logs every step to stdout for real-time monitoring.

| Method | Role |
|--------|------|
| `start(task)` | Logs task start |
| `beat(type, title, detail)` | Logs each step with emoji |
| `done(result)` | Logs completion |
| `error(msg)` | Logs errors |

### 3. ConversationMemory (`memory.py`)
Persists conversation history to disk (JSON).

| Method | Role |
|--------|------|
| `add_entry(role, content)` | Adds entry to history |
| `get_context(max_entries)` | Returns recent context for LLM |
| `save()` | Writes to `.inner-monologue-memory/` |
| `load()` | Reads from disk on startup |

### 4. SelfReflection (`self_reflection.py`)
Analyzes past interactions to build user profile.

| Method | Role |
|--------|------|
| `reflect(history)` | Extracts preferences from history |
| `get_insights()` | Returns user profile summary |

### 5. HITL (`hitl.py`)
Human-in-the-Loop via flag files in workspace.

| Method | Role |
|--------|------|
| `flag_in_progress(msg)` | Writes `.hitl-flags/IN_PROGRESS` |
| `flag_ready_for_review(result)` | Writes `READY_FOR_REVIEW.txt` |
| `clear_flags()` | Cleans up flag files |

## Data Flow

```
User Task
    │
    ▼
InnerMonologueAgent.run(task)
    │
    ├─▶ Heartbeat.start(task)
    ├─▶ Memory.add_entry("user", task)
    │
    └─▶ _loop()
            │
            ├─▶ [THINK] _build_think_prompt()
            │       └─▶ _call_llm_structured(prompt, "thought")
            │               └─▶ _call_llm() → LLM (Mistral/Groq/Mock)
            │
            ├─▶ [ACT]  _build_act_prompt(thought)
            │       └─▶ _call_llm_structured(prompt, "action")
            │               └─▶ _call_llm() → LLM
            │
            ├─▶ [OBSERVE] _observe(action_type, content)
            │       ├─▶ "terminal" → subprocess.run()
            │       ├─▶ "file"     → read/write/list files
            │       ├─▶ "code"     → log code change
            │       └─▶ "done"     → _finalize()
            │
            └─▶ loop until done or max_rounds (50)
```

## LLM Integration

```
                    ┌─────────────────────────┐
                    │     _call_llm()         │
                    └──────────┬──────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
         MockLLM          litellm          requests
        (testing)      (recommended)      (fallback)
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
          Mistral        Groq         Z.ai
       (primary)     (alternative)  (backup)
```

### Provider Config

| Provider | Model | Env Key | Status |
|----------|-------|---------|--------|
| Mistral | `mistral/mistral-large-latest` | `MISTRAL_API_KEY` | ✅ Primary |
| Groq | `groq/llama-3.3-70b-versatile` | `GROQ_API_KEY` | ✅ Alternative |
| Z.ai | (litellm compatible) | `MISTRAL_API_KEY` | ❓ Untested |
| Mock | — | — | ✅ Testing |

## File Structure

```
inner_monologue/
├── __init__.py          # Package init
├── agent.py             # Core ReAct Loop + LLM calls
├── heartbeat.py         # Real-time logging
├── memory.py            # Conversation persistence
├── self_reflection.py   # User profile builder
├── hitl.py              # Human-in-the-Loop flags
├── main.py              # CLI entry point
├── ARCHITECTURE.md      # This file
├── README.md            # Usage guide
└── ecosystem.config.cjs # PM2 config
```

## Key Design Decisions

1. **JSON-only responses** — LLM must output valid JSON. No free text. Prevents hallucination.
2. **Single system message** — Mistral API doesn't support multiple system roles. Everything in one message.
3. **Flag files for HITL** — Simple file-based protocol. No need for database or websocket.
4. **Subprocess for terminal** — Direct bash execution. No Docker-in-Docker complexity.
5. **Memory to disk** — JSON files in `.inner-monologue-memory/`. Simple, portable, debuggable.

## Error Handling

| Scenario | Handling |
|----------|----------|
| Rate limit (429) | Retry with same command |
| Stuck loop (3x same result) | Auto-done with "ติด loop" |
| JSON parse error | Retry up to 3 times with error prompt |
| Max rounds exceeded | Force done with warning |
| Missing API key | Fallback to MockLLM |
