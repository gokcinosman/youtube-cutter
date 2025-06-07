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

def download_full_video(url, full_output_path):
    """Downloads the full video from the specified URL to the given full_output_path."""
    print(f"▶ video_cutter_lib: Downloading full video: {url} -> {full_output_path}")
    
    command = [
        "yt-dlp",
        "--no-playlist",
        "--merge-output-format", "mp4", # Ensure mp4 format
        "-o", full_output_path, # Specify the exact output file path and name
        "--print", "filename", # Print the final resolved filename (should match full_output_path)
        url
    ]
    try:
        # Raises CalledProcessError on error.
        # We need to capture stdout to confirm the filename.
        result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        # The last line of stdout should be the filename yt-dlp used.
        # It should match full_output_path.
        confirmed_output_path = result.stdout.strip().splitlines()[-1] 
        
        print(f"▶ video_cutter_lib: Full video download command output:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        if confirmed_output_path != full_output_path:
            # This case should ideally not happen if yt-dlp respects -o as expected.
            print(f"⚠️ video_cutter_lib: Confirmed output path '{confirmed_output_path}' differs from requested '{full_output_path}'. Using confirmed path.")
        print(f"▶ video_cutter_lib: Full video download complete: {confirmed_output_path}")
        return confirmed_output_path # Return the actual path yt-dlp reported
    except subprocess.CalledProcessError as e:
        print(f"❌ video_cutter_lib: Full video download error: {e}")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
        raise  # Propagate the error to main.py
    except Exception as e:
        print(f"❌ video_cutter_lib: An unexpected error occurred during full video download: {e}")
        raise


# main() function and if __name__ == "__main__": block removed.
# tempfile.TemporaryDirectory() and output_video path management will be handled by the main plugin (main.py).
