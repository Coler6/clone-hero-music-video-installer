"""
Clone Hero Music Video Sync Tool
--------------------------------
Downloads and syncs YouTube music videos to Clone Hero song folders
by detecting the offset between the video audio and the song stems.
"""

import os
import subprocess
import tempfile
import argparse
import configparser

import yt_dlp
import numpy as np
import librosa
from scipy.spatial.distance import cdist
from scipy.signal import medfilt, correlate


def detect_audio_offset(combined_audio_path, video_path, duration=30.0, debug=True):
    """Offset detection between combined audio stems and video audio."""
    sr = 22050
    hop_length = 512

    try:
        # --- 1) Load audio (limit song to duration; load more of video)
        song_audio, _ = librosa.load(combined_audio_path, sr=sr, mono=True, duration=duration)
        video_audio, _ = librosa.load(video_path, sr=sr, mono=True, duration=max(duration * 2, duration + 20))

        if len(song_audio) < 2048 or len(video_audio) < 2048:
            if debug:
                print("Audio too short for robust detection; returning 0")
            return 0.0

        #2 Compute onset strength envelopes
        song_onset_env = librosa.onset.onset_strength(y=song_audio, sr=sr, hop_length=hop_length)
        video_onset_env = librosa.onset.onset_strength(y=video_audio, sr=sr, hop_length=hop_length)

        #3 Denoise onset envelopes with median filter
        k = int(max(1, round(sr / hop_length / 2)))
        if k % 2 == 0:
            k += 1
        song_env_d = song_onset_env - medfilt(song_onset_env, kernel_size=k)
        video_env_d = video_onset_env - medfilt(video_onset_env, kernel_size=k)

        # Rectify and normalize
        song_env_d = np.clip(song_env_d, 0, None)
        video_env_d = np.clip(video_env_d, 0, None)
        song_env_d /= np.max(song_env_d) + 1e-9
        video_env_d /= np.max(video_env_d) + 1e-9

        if np.max(song_env_d) < 1e-4 or np.max(video_env_d) < 1e-4:
            if debug:
                print("Onset envelopes too small -> fallback to chroma DTW")
            return _detect_offset_dtw(song_audio=song_audio, video_audio=video_audio,
                                      sr=sr, hop_length=hop_length, duration=duration, debug=debug)

        #4 FFT-based correlation
        corr = correlate(video_env_d, song_env_d, mode='full', method='fft')
        best_idx = np.argmax(corr)
        lag_frames = best_idx - (len(song_env_d) - 1)
        offset_seconds = lag_frames * hop_length / sr
        peak_value = corr[best_idx]

        if debug:
            print(f"Onset-corr candidate offset = {offset_seconds:.3f}s, peak={float(peak_value):.5f}")

        #5 Heuristic check
        flat_sorted = np.sort(corr)
        median_side = np.median(flat_sorted[:max(1, int(len(flat_sorted) * 0.5))])
        if peak_value < max(0.05, 5.0 * (median_side + 1e-12)):
            if debug:
                print("Correlation peak too weak -> using DTW chroma fallback")
            return _detect_offset_dtw(song_audio_path=combined_audio_path, video_audio_path=video_path,
                                      duration=duration, debug=debug)

        return offset_seconds

    except Exception as e:
        if debug:
            import traceback
            traceback.print_exc()
        return _detect_offset_dtw(song_audio_path=combined_audio_path, video_audio_path=video_path,
                                  duration=duration, debug=debug)


def _detect_offset_dtw(song_audio_path=None, video_audio_path=None, song_audio=None, video_audio=None,
                       sr=22050, hop_length=512, duration=30.0, debug=False):
    """
    Internal DTW chroma fallback.
    Returns offset_seconds where video starts relative to song.
    """
    if song_audio is None or video_audio is None:
        song_audio, _ = librosa.load(song_audio_path, sr=sr, mono=True, duration=duration)
        video_audio, _ = librosa.load(video_audio_path, sr=sr, mono=True, duration=max(duration * 3, duration + 30))

    try:
        song_chroma = librosa.feature.chroma_cqt(y=song_audio, sr=sr)
        video_chroma = librosa.feature.chroma_cqt(y=video_audio, sr=sr)
    except Exception:
        song_chroma = librosa.feature.chroma_stft(y=song_audio, sr=sr)
        video_chroma = librosa.feature.chroma_stft(y=video_audio, sr=sr)

    sc = song_chroma / (np.linalg.norm(song_chroma, axis=0, keepdims=True) + 1e-9)
    vc = video_chroma / (np.linalg.norm(video_chroma, axis=0, keepdims=True) + 1e-9)
    cost = cdist(sc.T, vc.T, metric='cosine')

    try:
        D, wp = librosa.sequence.dtw(C=cost, backtrack=True)
    except Exception:
        song_vec = np.mean(sc, axis=0)
        video_vec = np.mean(vc, axis=0)
        corr = correlate(video_vec, song_vec, mode='full', method='fft')
        lag = np.argmax(corr) - (len(song_vec) - 1)
        offset_seconds = lag * hop_length / sr
        if debug:
            print(f"DTW failed; used mean-chroma corr -> offset {offset_seconds:.3f}s")
        return offset_seconds

    wp = np.array(wp)
    if wp.shape[1] == 2:
        wp = wp.T
    song_idx, vid_idx = wp[:, 0], wp[:, 1]
    candidates = vid_idx[song_idx <= 2]
    candidate_vid_idx = int(np.median(candidates)) if len(candidates) else int(vid_idx[np.argmin(song_idx)])
    offset_seconds = librosa.frames_to_time(candidate_vid_idx, sr=sr, hop_length=hop_length)

    if debug:
        print(f"DTW mapping offset: {offset_seconds:.3f}s")
    return offset_seconds

def combine_audio_stems_pcm(song_folder, duration=10.0):
    """Combine all audio stems into a single PCM WAV file."""
    audio_files = [os.path.join(song_folder, f) for f in os.listdir(song_folder)
                   if f.lower().endswith(('.opus', '.ogg', '.mp3', '.wav'))]
    if not audio_files:
        print("No audio files found.")
        return None

    temp_wavs = []
    for f in audio_files:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        subprocess.run([
            "ffmpeg", "-y", "-i", f,
            "-t", str(duration), "-ac", "1", "-ar", "22050",
            "-f", "wav", "-acodec", "pcm_s16le", tmp
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        temp_wavs.append(tmp)

    mixed_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    inputs = sum((["-i", w] for w in temp_wavs), [])
    filter_complex = f"amix=inputs={len(temp_wavs)}:normalize=0:duration=longest"

    subprocess.run([
        "ffmpeg", *inputs, "-filter_complex", filter_complex,
        "-ar", "22050", "-ac", "1", "-f", "wav", "-acodec", "pcm_s16le", "-y", mixed_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for w in temp_wavs:
        try: os.remove(w)
        except: pass

    return mixed_path


def download_video(query, output_path):
    """Download a YouTube music video as MP4."""
    ydl_opts = {
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
            {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'},
            {'key': 'FFmpegMetadata', 'add_metadata': False},
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"ytsearch1:{query} music video"])


def update_song_ini(ini_path, offset_seconds):
    """Add or update video_start_time in song.ini."""
    offset_ms = int(round(offset_seconds * 1000))
    config = configparser.ConfigParser()

    with open(ini_path, 'r', encoding='utf-8', errors='ignore') as f:
        config.read_file(f)

    if not config.has_section('song'):
        config.add_section('song')

    config.set('song', 'video_start_time', str(offset_ms))

    with open(ini_path, 'w', encoding='utf-8') as f:
        config.write(f)

    print(f"Saved video_start_time = {offset_ms} (milliseconds) to song.ini")

def main(song_folder, duration=10.0):
    ini_path = os.path.join(song_folder, 'song.ini')
    if not os.path.exists(ini_path):
        print("No song.ini found.")
        return

    config = configparser.ConfigParser()
    with open(ini_path, 'r', encoding='utf-8', errors='ignore') as f:
        config.read_file(f)

    title = config['song'].get('name', None)
    if not title:
        print("Could not read song title from song.ini.")
        return

    print(f"Downloading video for: {title}")
    download_video(title, song_folder)

    video_path = next((os.path.join(song_folder, f)
                      for f in os.listdir(song_folder)
                      if f.startswith('video.') and f.endswith('.mp4')), None)
    if not video_path:
        print("Video download failed.")
        return

    print("Combining all audio stems into one track...")
    combined_audio = combine_audio_stems_pcm(song_folder, duration=duration)
    if not combined_audio:
        print("No audio files to combine. Exiting.")
        return

    print("Detecting offset between combined audio and video...")
    detected_offset = detect_audio_offset(combined_audio, video_path, duration=duration)
    print(f"Detected offset: {detected_offset:.3f} seconds")

    try:
        os.remove(combined_audio)
    except:
        pass

    update_song_ini(ini_path, detected_offset)
    print("Done! Added offset to song.ini")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Clone Hero Music Video Sync Tool")
    parser.add_argument("song_folder", help="Path to the Clone Hero song folder")
    parser.add_argument("--duration", type=float, default=10.0,
                        help="Duration (in seconds) of audio used for offset detection (default: 10)")
    args = parser.parse_args()
    main(args.song_folder, args.duration)