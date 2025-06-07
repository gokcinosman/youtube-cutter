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

def download_full_video(url, output_dir):
    """Downloads the full video from the specified URL to the output_dir, using video title as filename."""
    print(f"▶ video_cutter_lib: Downloading full video: {url} -> {output_dir}")
    
    # yt-dlp will save the file in output_dir with the name derived from the video title.
    # We use --print filename to get the actual path of the downloaded file.
    # The -P option sets the output path template, which in this case is just the directory.
    # yt-dlp will append the filename (like title.ext) to this path.
    command = [
        "yt-dlp",
        "--no-playlist",
        "--merge-output-format", "mp4", # Ensure mp4 format
        "-P", output_dir, # Set output directory
        # "-o", "%(title)s.%(ext)s", # Let yt-dlp determine filename from title, already default with -P
        "--print", "filename", # Print the final resolved filename
        url
    ]
    try:
        # Raises CalledProcessError on error.
        # We need to capture stdout to get the filename.
        result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        downloaded_file_path = result.stdout.strip().splitlines()[-1] # Get the last line of stdout, which should be the filename
        
        # yt-dlp with -P might print the full path directly, or just the filename relative to CWD if -P wasn't effective as expected.
        # Let's ensure the path is absolute and correct.
        # If yt-dlp prints an absolute path, great. If it prints a relative one (e.g. if -P was ignored and it saved to CWD)
        # then os.path.join(output_dir, downloaded_file_path) might be needed.
        # However, with -P, yt-dlp should handle placing it in output_dir and printing the full path or path relative to output_dir.
        # The --print filename usually gives the full path when -P is used.

        print(f"▶ video_cutter_lib: Full video download command output:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        print(f"▶ video_cutter_lib: Full video download complete: {downloaded_file_path}")
        return downloaded_file_path # Return the actual path of the downloaded file
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
