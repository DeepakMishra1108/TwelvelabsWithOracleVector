"""FFmpeg helper utilities: cutting, concatenation, thumbnail extraction."""
import shutil
import subprocess
import tempfile
import os
import pathlib


def _find_ffmpeg():
    return shutil.which('ffmpeg')


def cut_segment(input_url, start, end, out_path, timeout=None):
    ffmpeg_bin = _find_ffmpeg()
    if not ffmpeg_bin:
        raise RuntimeError('ffmpeg not found on PATH')
    cmd = [ffmpeg_bin, '-y', '-i', input_url, '-ss', str(start), '-to', str(end), '-c', 'copy', out_path]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return proc.returncode, proc.stdout.decode('utf-8', errors='replace'), proc.stderr.decode('utf-8', errors='replace')


def concat_segments(segment_paths, out_path, timeout=None):
    ffmpeg_bin = _find_ffmpeg()
    if not ffmpeg_bin:
        raise RuntimeError('ffmpeg not found on PATH')
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as f:
        list_path = f.name
        for p in segment_paths:
            f.write(f"file '{p}'\n")
    cmd = [ffmpeg_bin, '-y', '-f', 'concat', '-safe', '0', '-i', list_path, '-c', 'copy', out_path]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    try:
        os.unlink(list_path)
    except Exception:
        pass
    return proc.returncode, proc.stdout.decode('utf-8', errors='replace'), proc.stderr.decode('utf-8', errors='replace')


def extract_frame_bytes(input_url, time_offset=0.5, timeout=15):
    ffmpeg_bin = _find_ffmpeg()
    if not ffmpeg_bin:
        return None, 'ffmpeg not found'
    cmd = [ffmpeg_bin, '-ss', str(time_offset), '-i', input_url, '-frames:v', '1', '-q:v', '2', '-f', 'image2', '-']
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        if proc.returncode != 0:
            return None, proc.stderr.decode('utf-8', errors='replace')
        return proc.stdout, None
    except Exception as e:
        return None, str(e)
