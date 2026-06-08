# Wav2Lip Colab Notebook — Offline Lip-Sync for TikTok UGC Videos

This notebook runs Wav2Lip inference in Google Colab.  
It processes a video and an audio file to produce a lip-synced output video.

---

## Step 1: Mount Google Drive

```python
from google.colab import drive
drive.mount('/content/drive')
```

Create a working folder:

```python
import os
WORK_DIR = "/content/wav2lip_work"
os.makedirs(WORK_DIR, exist_ok=True)
os.chdir(WORK_DIR)
print(f"Working directory: {WORK_DIR}")
```

---

## Step 2: Install Dependencies

```python
!pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
!pip install -q opencv-python==4.8.1.78
!pip install -q face_recognition
!pip install -q pandas
!pip install -q gdown
!pip install -q moviepy
```

---

## Step 3: Clone Wav2Lip Repository

```python
# Clone official Wav2Lip repo
!git clone https://github.com/Rudrabha/Wav2Lip.git /content/Wav2Lip
%cd /content/Wav2Lip

# Download the pre-trained model
!wget 'https://iiitaphyd-my.sharepoint.com/personal/radrabha_m_research_iiit_ac_in/_layouts/15/download.aspx?share=EdjI7bZlgApMqsVoEUUXpLsBxqXbn5z8VTmoxp55YNDcIA' -O 'checkpoints/wav2lip_gan.pth'
```

---

## Step 4: Upload Your Video and Audio Files

Upload your source video (with a speaking face) and the target audio (generated TTS).

```python
from google.colab import files

print("Upload your VIDEO file (MP4, MOV, etc.):")
uploaded_video = files.upload()

print("\nUpload your AUDIO file (MP3, WAV, etc.):")
uploaded_audio = files.upload()

# Get filenames
video_path = list(uploaded_video.keys())[0]
audio_path = list(uploaded_audio.keys())[0]
```

---

## Step 5: Prepare Input Files

```python
import shutil

# Copy files to Wav2Lip directory
input_video = "/content/Wav2Lip/input_video.mp4"
input_audio = "/content/Wav2Lip/input_audio.wav"

# Convert video if needed
if not video_path.endswith('.mp4'):
    !ffmpeg -i "{video_path}" -c:v libx264 -crf 23 -c:a aac "{input_video}" -y
else:
    shutil.copy(video_path, input_video)

# Convert audio to WAV (required by Wav2Lip)
!ffmpeg -i "{audio_path}" -acodec pcm_s16le -ac 1 -ar 16000 "{input_audio}" -y
```

---

## Step 6: Run Wav2Lip Inference

```python
%cd /content/Wav2Lip

!python inference.py \
    --checkpoint_path checkpoints/wav2lip_gan.pth \
    --face "{input_video}" \
    --audio "{input_audio}" \
    --outfile results/output_video.mp4 \
    --pads 0 0 0 0 \
    --resize_factor 2
```

**Parameters explained:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--checkpoint_path` | Path to Wav2Lip model checkpoint | (required) |
| `--face` | Input video file | (required) |
| `--audio` | Input audio file (WAV, 16kHz mono) | (required) |
| `--outfile` | Output video path | `results/output_video.mp4` |
| `--pads` | Pad face region (top, bottom, left, right) | `0 0 0 0` |
| `--resize_factor` | Downscale factor for speed (1=full, 2=half) | `2` |
| `--nosync` | Disable audio-video sync check | (optional) |

---

## Step 7: Download the Result

```python
from google.colab import files
import os

output_path = "/content/Wav2Lip/results/output_video.mp4"
if os.path.exists(output_path):
    file_size = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Output video: {output_path} ({file_size:.1f} MB)")
    files.download(output_path)
else:
    print("Error: Output file not found!")
```

---

## Step 8: (Optional) Save to Google Drive

```python
import shutil

drive_path = "/content/drive/MyDrive/wav2lip_output.mp4"
shutil.copy(output_path, drive_path)
print(f"Saved to Google Drive: {drive_path}")
```

---

## Troubleshooting

### CUDA Out of Memory

```python
# Reduce resize factor or use smaller resolution
!python inference.py \
    --checkpoint_path checkpoints/wav2lip_gan.pth \
    --face "{input_video}" \
    --audio "{input_audio}" \
    --outfile results/output_video.mp4 \
    --resize_factor 4  # Higher number = lower quality but less memory
```

### Face Not Detected

```python
# Adjust padding to help face detection
!python inference.py \
    --checkpoint_path checkpoints/wav2lip_gan.pth \
    --face "{input_video}" \
    --audio "{input_audio}" \
    --outfile results/output_video.mp4 \
    --pads 0 20 0 20  # Add top/bottom padding
```

### Colab Disconnects

- Run inference during non-peak hours
- Use Chrome with "Keep awake" extensions
- Save intermediate results to Google Drive periodically

---

## Integration with TikTok UGC Studio

After downloading the Wav2Lip output, you can:

1. Upload the synced video to the UGC Studio via the API
2. Use `composer.py` to add background music:
   ```python
   from composer import add_sound_effects
   add_sound_effects(
       video_path="wav2lip_output.mp4",
       sound_path="background_music.mp3",
       output_path="final_ugc_video.mp4",
       volume=0.3,
       mix=True
   )
   ```
3. Use `merge_audio_video` with offset fine-tuning:
   ```python
   from composer import merge_audio_video
   merge_audio_video(
       video_path="original_video.mp4",
       audio_path="tts_audio.mp3",
       output_path="synced_video.mp4",
       lip_sync_offset=0.0
   )
   ```
