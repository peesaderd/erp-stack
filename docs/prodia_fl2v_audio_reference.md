# Prodia Wan 2.7 FL2V + Audio — Official Parameter Reference

> **Source**: Official code sample provided by owner (2026-08-19). This is the **single ground truth** for the
> `inference.wan2-7.img2vid.v1` job with first_frame → last_frame interpolation + lip-sync audio.
> Use this to verify our pipeline (`pipeline_affiliate.py` STEP 8 + `prodia_client.py`) instead of guessing/arguing.

## Official JS sample (verbatim)

```javascript
import fs from "node:fs/promises";
import { createProdia } from "prodia/v2";

const prodia = createProdia({
  token: process.env.PRODIA_TOKEN
});

(async () => {
  const inputs = [
    await fs.readFile("first_frame.png"),
    await fs.readFile("last_frame.png"),
    await fs.readFile("speech.mp3")
  ];

  const job = await prodia.job({
    "type": "inference.wan2-7.img2vid.v1",
    "config": {
      "image": "first_frame.png",
      "last_frame": "last_frame.png",
      "audio": "speech.mp3",
      "prompt": "A cat walking through a garden",
      "negative_prompt": "low resolution, error, worst quality, deformed",
      "resolution": "720P",
      "duration": 5,
      "prompt_extend": true
    }
  }, {
    accept: "video/mp4",
    inputs: inputs
  });

  const image = await job.arrayBuffer();

  await fs.writeFile("output.mp4", new Uint8Array(image));
})();
```

## Field mapping (what our pipeline must send)

| Config field | Official | Our pipeline equivalent | Notes |
|--------------|----------|------------------------|-------|
| `type` | `inference.wan2-7.img2vid.v1` | same | async job |
| `image` | `first_frame.png` (file name in multipart) | `first_frame` bytes | must reference the multipart filename |
| `last_frame` | `last_frame.png` | `last_frame` bytes | start→end interpolation target |
| `audio` | `speech.mp3` | `audio_bytes` (16k mono wav per owner) | lip-sync; multipart filename must match |
| `prompt` | short scene prompt | prompt (single scene) | |
| `negative_prompt` | short | **HARD CAP 500 chars** (Prodia limit) | len 500 passes / 501 fails |
| `resolution` | `720P` | `720P` | |
| `duration` | 5 | 5–15 | |
| `prompt_extend` | `true` | `true` | |

## Multipart upload (3 inputs, order matters)
1. `first_frame.png`  → `inputs[0]`
2. `last_frame.png`   → `inputs[1]`
3. `speech.mp3`       → `inputs[2]`

`config.image` / `config.last_frame` / `config.audio` reference the **multipart file names** (`first_frame.png` etc.).
The client reads these files by name from the uploaded parts and feeds them to the model.

## 🔴 Owner-stated intent (2026-08-19 13:44)
- The **"audio doesn't enter" symptom = mouth not matching the audio (lip-sync mismatch)** — NOT a file/merge issue.
- Owner is frustrated from repeating this; stop re-diagnosing wrong things. Use this doc as reference.

## Related constraints (from MEMORY)
- Do **NOT** send `negative_prompt`/`ratio` for img2vid (only for t2i) — but `negative_prompt` IS allowed here (official sample includes it), keep it ≤ 500 chars.
- Audio must be **16kHz mono WAV** (`-ac 1 -ar 16000 -c:a pcm_s16le`) before sending.
- Pipeline returns aac 24000Hz mono in output (verified).
