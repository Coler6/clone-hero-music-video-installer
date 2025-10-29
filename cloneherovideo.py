import os
import sys
import subprocess
import configparser
import yt_dlp
import numpy as np
import librosa
import soundfile as sf
import tempfile

from scipy.io import wavfile

def detect_audio_offset(combined_audio_path, video_path, duration=10.0):
    import tempfile, subprocess, os, numpy as np, soundfile as sf

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
        extracted_audio = tmp_audio.name

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-ac", "1", "-ar", "22050",
        "-t", str(duration),
        "-f", "wav", "-acodec", "pcm_s16le", extracted_audio
    ]
    res = subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-ac", "1", "-ar", "22050",
        "-t", str(duration),
        "-f", "wav", "-acodec", "pcm_s16le", extracted_audio
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if res.returncode != 0:
        print("FFmpeg failed:\n", res.stderr.decode())
        return 0.0

    # Load audio safely
    song_audio, sr1 = sf.read(combined_audio_path)
    video_audio, sr2 = sf.read(extracted_audio)

    # Normalize
    song_audio /= np.max(np.abs(song_audio)) + 1e-9
    video_audio /= np.max(np.abs(video_audio)) + 1e-9

    # Cross-correlation
    correlation = np.correlate(video_audio, song_audio, mode="full")
    lag = np.argmax(correlation) - len(song_audio)
    offset_seconds = lag / sr1

    os.remove(extracted_audio)
    return offset_seconds


def combine_audio_stems_pcm(song_folder, duration=10.0):
    """
    Combine all audio stems into a single PCM WAV file compatible with scipy.io.wavfile.
    Only uses the first `duration` seconds.
    """
    audio_files = [
        os.path.join(song_folder, f)
        for f in os.listdir(song_folder)
        if f.lower().endswith(('.opus', '.ogg', '.mp3', '.wav'))
    ]
    if not audio_files:
        print("No audio files found.")
        return None

    # Convert stems individually to temp PCM WAV files
    temp_wavs = []
    for f in audio_files:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        subprocess.run([
            "ffmpeg", "-y", "-i", f,
            "-t", str(duration),
            "-ac", "1",
            "-ar", "22050",
            "-f", "wav",
            "-acodec", "pcm_s16le",
            tmp
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        temp_wavs.append(tmp)

    # Combine all temp WAVs with ffmpeg
    mixed_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    inputs = []
    for w in temp_wavs:
        inputs += ["-i", w]

    filter_complex = f"amix=inputs={len(temp_wavs)}:normalize=0:duration=longest"

    subprocess.run([
        "ffmpeg",
        *inputs,
        "-filter_complex", filter_complex,
        "-ar", "22050",
        "-ac", "1",
        "-f", "wav",
        "-acodec", "pcm_s16le",
        "-y", mixed_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Clean up temp WAVs
    for w in temp_wavs:
        try: os.remove(w)
        except: pass

    return mixed_path


def download_video(query, output_path):
    """Download a YouTube video as MP4 (H.264 or H.265), no metadata."""
    ydl_opts = {
        # Prefer h264 or h265 (avoid av1/vp9), fallback to mp4 if not available
        'format': (
            'bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/'
            'bestvideo[vcodec^=hev1][ext=mp4]+bestaudio[ext=m4a]/'
            'bestvideo[vcodec^=hvc1][ext=mp4]+bestaudio[ext=m4a]/mp4'
        ),
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': False,
        'outtmpl': os.path.join(output_path, 'video.%(ext)s'),
        'postprocessors': [
            {
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            },
            {
                'key': 'FFmpegMetadata',
                'add_metadata': False,
            },
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"ytsearch1:{query} music video"])


def clear_metadata(file_path):
    """Remove all metadata from a video using ffmpeg."""
    temp_output = file_path.replace('.mp4', '_clean.mp4')
    subprocess.run([
        'ffmpeg', '-i', file_path,
        '-map', '0', '-map_metadata', '-1', '-c', 'copy', temp_output,
        '-y'
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.replace(temp_output, file_path)

def sync_video(video_path, offset_seconds):
    """Shift video timing to match offset."""
    output_path = video_path.replace('.mp4', '_synced.mp4')
    if offset_seconds >= 0:
        # Delay video relative to audio
        subprocess.run([
            'ffmpeg', '-i', video_path,
            '-itsoffset', str(offset_seconds),
            '-i', video_path, '-map', '1:v', '-map', '0:a?',
            '-c', 'copy', output_path, '-y'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        # Trim the start of the video
        subprocess.run([
            'ffmpeg', '-ss', str(abs(offset_seconds)),
            '-i', video_path, '-c', 'copy', output_path, '-y'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.replace(output_path, video_path)

def read_song_ini(ini_path):
    """Read song.ini and extract song title and video offset."""
    config = configparser.ConfigParser()

    # Safely read the file with fallback for encoding
    try:
        with open(ini_path, 'r', encoding='utf-8', errors='ignore') as f:
            config.read_file(f)
    except Exception as e:
        print(f"Error reading song.ini: {e}")
        return None, 0.0

    title = None
    offset = 0.0

    if 'song' in config:
        title = config['song'].get('name', None)
        offset = float(config['song'].get('video_offset', 0) or 0)
    else:
        # Sometimes song.ini has no [song] section
        for section in config.sections():
            if 'name' in config[section]:
                title = config[section]['name']
            if 'video_offset' in config[section]:
                offset = float(config[section].get('video_offset', 0) or 0)
    return title, offset

def update_song_ini(ini_path, offset_seconds):
    """Add or update video_start_time in song.ini (stored in milliseconds)."""
    offset_ms = int(round(offset_seconds * 1000))  # convert to ms

    config = configparser.ConfigParser()
    with open(ini_path, 'r', encoding='utf-8', errors='ignore') as f:
        config.read_file(f)

    if not config.has_section('song'):
        config.add_section('song')

    config.set('song', 'video_start_time', str(offset_ms))

    with open(ini_path, 'w', encoding='utf-8') as f:
        config.write(f)

    print(f"Saved video_start_time = {offset_ms} (milliseconds) to song.ini")

def main(song_folder):
    ini_path = os.path.join(song_folder, 'song.ini')
    if not os.path.exists(ini_path):
        print("No song.ini found.")
        return

    title, offset = read_song_ini(ini_path)
    if not title:
        print("Could not read song title from song.ini.")
        return

    print(f"Downloading video for: {title}")
    download_video(title, song_folder)

    video_path = next((os.path.join(song_folder, f) for f in os.listdir(song_folder) if f.startswith('video.') and f.endswith('.mp4')), None)
    if not video_path:
        print("Video download failed.")
        return

    print("Combining all audio stems into one track...")
    combined_audio = combine_audio_stems_pcm(song_folder, duration=10.0)
    if not combined_audio:
        print("No audio files to combine. Exiting.")
        return
    print("Combined audio file:", combined_audio)
    subprocess.run(["ffmpeg", "-i", combined_audio])
    print("File size (bytes):", os.path.getsize(combined_audio))
    print("Detecting offset between combined audio and video...")
    detected_offset = detect_audio_offset(combined_audio, video_path, duration=10.0)
    print(f"Detected offset: {detected_offset:.3f} seconds")

    try:
        os.remove(combined_audio)
    except:
        pass

    update_song_ini(ini_path, detected_offset)

    print("Done! Added offset to song.ini")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python sync_video.py <song_folder_path>")
    else:
        main(sys.argv[1])
