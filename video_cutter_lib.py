import subprocess
import os
# import tempfile # Bu artık main.py'de yönetilecek
# import shutil # Bu artık main.py'de yönetilecek

def download_video(url, output_path):
    """Downloads the video from the specified URL."""
    print(f"▶ video_cutter_lib: Downloading video: {url} -> {output_path}")
    command = [
        "yt-dlp",
        "--no-playlist",
        # "-f", "best", # Removed as per yt-dlp suggestion
        "--merge-output-format", "mp4",
        "-o", output_path,
        url
    ]
    try:
        # Raises CalledProcessError on error.
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"▶ video_cutter_lib: Video download command output:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        print("▶ video_cutter_lib: Video download complete.")
    except subprocess.CalledProcessError as e:
        print(f"❌ video_cutter_lib: Video download error: {e}")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
        raise  # Propagate the error to main.py

def cut_video(input_path, start_time, end_time, output_path):
    """Cuts the video in the specified time range."""
    print(f"▶ video_cutter_lib: Cutting video: {input_path} [{start_time}-{end_time}] -> {output_path}")
    command = [
        "ffmpeg",
        "-ss", start_time,
        "-to", end_time,
        "-i", input_path,
        "-c", "copy",
        output_path
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"▶ video_cutter_lib: Video cutting command output:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        print("▶ video_cutter_lib: Video cutting complete.")
    except subprocess.CalledProcessError as e:
        print(f"❌ video_cutter_lib: Video cutting error: {e}")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
        raise # Propagate the error to main.py

# main() function and if __name__ == "__main__": block removed.
# tempfile.TemporaryDirectory() and output_video path management will be handled by the main plugin (main.py).
