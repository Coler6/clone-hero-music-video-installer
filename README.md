# Clone Hero Video Sync Tool

Automatically download music videos and sync them with Clone Hero songs. I used a fuck ton of chatgpt to make this but it works. Some music videos don't work since they used cropped versions of the song like Smells Like Teen Spirit.  You can use onyx to convert .sng files into folders.  Idk if it works for everything but it worked for every song I used.

---

## Features

- Downloads YouTube music videos in MP4 (H.264/H.265) format.  
- Combines multiple audio stems (`.opus`, `.ogg`, `.mp3`, `.wav`) into a single track.  
- Detects audio/video offset using the first 5–10 seconds for fast processing.  
- Writes `video_start_time` (in **milliseconds**) directly to `song.ini`.  
- Works with Windows file paths and standard Clone Hero song folder structures.

---

## Issues
It can't automatically sync it if they have a longer intro. You can sync it manually by uploading the song and audio file to mircosoft clipchamp. Detect the audio from the video. Then match the audio waves up. Once you do that well enough you can see the offset by hovering over where the video audio starts. Then go to song.ini and change video_start_time = ____ with that timestamp in ms.

---

## Requirements

- Python 3.10+  
- [FFmpeg](https://ffmpeg.org/) installed and in your system PATH or the same folder as cloneherovideo.py
- Python packages:

```bash
pip install numpy soundfile librosa yt-dlp
```

---


```bash
python cloneherovideo.py "D:\songs\My Chemical Romance - Teenagers (Harmonix) --duration"
```

What the script does:
1. Downloads the music video (MP4, H.264/H.265) without metadata.  
2. Converts and combines all audio stems into a single PCM WAV (mono, 22.05 kHz).  
3. Extracts the first N seconds (default 10s) of audio from video and combined stems.  
4. Cross-correlates the two clips to detect offset.
5. Warning this takes a long time at "Detecting offset between combined audio and video..." give it like 5 minutes.
6. Writes `video_start_time = <ms>` to `song.ini` (milliseconds).
