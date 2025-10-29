# Clone Hero Video Sync Tool

Automatically download music videos and sync them with Clone Hero songs. I used a fuck ton of chatgpt to make this but it works. Some music videos don't work since they used cropped versions of the song like Smells Like Teen Spirit.  You can use onyx to convert .sng files into folders.  Idk if it works for everything but it worked for every song I used.

---

## Manual Sync (If Auto Detection Fails)

If the automatic syncing doesn’t work correctly, you can sync it manually using **Microsoft Clipchamp**:

1. Open **Clipchamp** and import:
   - The **video file** (downloaded to your song folder)
   - The **song audio file** (e.g. `song.opus` or `song.wav`). You might need to add all of audio files if the tracks are split up.
2. Drag both into the timeline.  
3. **Detach** the audio from the video (right-click → "Detach Audio").  
4. Align the waveforms visually — match the start of the music with the chart’s audio.  
5. Hover your mouse where the **video’s music** starts playing — note the timestamp in seconds.  
6. Convert that to milliseconds (e.g., 2.347 s → 2347 ms).  
7. Edit your `song.ini` and set: ```ini video_start_time = 2347```
8. Save it — Clone Hero will now sync the video properly.

---

## Features

- Downloads YouTube music videos in MP4 (H.264/H.265) format.  
- Combines multiple audio stems (`.opus`, `.ogg`, `.mp3`, `.wav`) into a single track.  
- Detects audio/video offset.
- Writes `video_start_time` (in **milliseconds**) directly to `song.ini`.  
- Works with Windows file paths and standard Clone Hero song folder structures.

---

## Requirements

- Python 3.10+  
- [FFmpeg](https://ffmpeg.org/) installed and in your system PATH or the same folder as cloneherovideo.py
- Python packages:

```bash
pip install numpy soundfile librosa yt-dlp
```

---

## Example
```bash
python cloneherovideo.py "D:\songs\My Chemical Romance - Teenagers (Harmonix)" --duration 5.0
```

What the script does:
1. Downloads the music video (MP4, H.264/H.265) without metadata.  
2. Converts and combines all audio stems into a single PCM WAV (mono, 22.05 kHz).  
3. Extracts the first N seconds (default 30s) of audio from video and combined stems.  
4. Cross-correlates the two clips to detect offset.
5. Could take a bit at "Detecting offset between combined audio and video...".
6. Writes `video_start_time = <ms>` to `song.ini` (milliseconds).
