# Clone Hero Video Sync Tool

Automatically download music videos and sync them with Clone Hero songs. This tool combines all audio stems from a song folder, detects the video/audio offset, and updates `song.ini` with the correct `video_start_time`.

---

## Features

- Downloads YouTube music videos in MP4 (H.264/H.265) format.  
- Combines multiple audio stems (`.opus`, `.ogg`, `.mp3`, `.wav`) into a single track.  
- Detects audio/video offset using the first 5–10 seconds for fast processing.  
- Writes `video_start_time` (in **milliseconds**) directly to `song.ini`.  
- Works with Windows file paths and standard Clone Hero song folder structures.

---

## Requirements

- Python 3.10+  
- [FFmpeg](https://ffmpeg.org/) installed and in your system PATH  
- Python packages:

```bash
pip install numpy soundfile librosa yt-dlp
```

---

## Usage

1. Put the script (`cloneherovideo.py`) somewhere convenient.  
2. Open Command Prompt (Windows).  
3. Run the script with the path to the song folder:

```bash
python cloneherovideo.py "D:\songs\My Chemical Romance - Teenagers (Harmonix)"
```

What the script does:
1. Downloads the music video (MP4, H.264/H.265) without metadata.  
2. Converts and combines all audio stems into a single PCM WAV (mono, 22.05 kHz).  
3. Extracts the first N seconds (default 10s) of audio from video and combined stems.  
4. Cross-correlates the two clips to detect offset.  
5. Writes `video_start_time = <ms>` to `song.ini` (milliseconds).

---

## Command-line options (example ideas)

You can modify the script to accept extra optional args (not included by default). Common options you might add:

- `--duration N` — number of seconds to use for offset detection (default 10).  
- `--batch` — process all subfolders inside a parent `songs` directory.  
- `--no-download` — skip downloading if `video.mp4` already exists.

---

## Troubleshooting

- **`Format not recognised` / `File format b'' not understood`**  
  - Ensure FFmpeg successfully created the temporary WAV files. If ffmpeg fails, the script prints ffmpeg stderr. Make sure the video file is *not open* in any player (Windows can lock files).  
- **Permission denied opening video file**  
  - Close any program that might be using the MP4 (media players, Explorer preview pane). Try running the ffmpeg command manually to confirm.  
- **Video does not play in Windows**  
  - The script forces H.264/H.265. If your player can't play the result, use VLC or install the AV1/HEVC extension for Windows.  
- **Offset detection returns 0**  
  - Increase the duration used for detection (try 15–20s) or ensure combined stems reflect the main mix (the script combines all stems by default). If stems are misaligned internally, detection may be less accurate.

---

## Implementation notes

- The script:
  - Forces MP4 output via yt-dlp and ffmpeg postprocessors.
  - Converts stems individually to PCM WAV (`pcm_s16le`) then mixes with `ffmpeg` `amix` to guarantee a compatible WAV for analysis.
  - Extracts video audio to PCM WAV and uses a cross-correlation method on short clips (fast and effective for studio audio vs video audio).
  - Writes `video_start_time` as an integer number of milliseconds to the `[song]` section of `song.ini`. If the section is missing, it will be created.

---

## Example `song.ini` change

Before:
```ini
[name]
...
```

After (script adds/updates):
```ini
[song]
video_start_time = 2347
```
(2347 = 2.347 seconds)

---

## License

MIT — see `LICENSE` in the repo.

---

## Want it prettier?

If you want, I can:
- Add a short animated GIF showing a run.  
- Add a `USAGE.md` with examples and troubleshooting logs.  
- Produce a full, ready-to-run `cloneherovideo.py` file in the repo and a sample test folder.

Tell me which and I’ll produce the files ready to paste.
