import subprocess
import os
import re

def _process_yt_dlp_output(process, progress_callback, action_name):
    """Helper to process Popen stdout for progress and collect all output."""
    all_stdout_lines = []
    if process.stdout:
        for line_bytes in iter(process.stdout.readline, b''):
            line = line_bytes.decode('utf-8', errors='replace').strip()
            if not line:
                continue
            all_stdout_lines.append(line)
            print(f"▶ video_cutter_lib ({action_name}): STDOUT line: {line}") # Log all lines for debugging
            
            if progress_callback:
                # Try to match our specific progress template
                match = re.search(r"YTC_PROGRESS:([\s\d\.]+%)", line)
                if match:
                    percentage = match.group(1).strip()
                    progress_callback(percentage)
                else:
                    # Fallback for default yt-dlp progress format if template fails
                    match_default = re.search(r"\[download\]\s+([\d\.]+%)", line)
                    if match_default:
                        percentage = match_default.group(1).strip()
                        progress_callback(percentage)
        process.stdout.close()
    
    process.wait() # Wait for the process to complete
    return process.returncode, all_stdout_lines

def download_video(url, output_path, progress_callback=None):
    """Downloads the video from the specified URL, with progress reporting."""
    print(f"▶ video_cutter_lib: Downloading video for cut: {url} -> {output_path}")
    command = [
        "yt-dlp",
        "--no-playlist",
        "--progress", # Enable progress output
        "--progress-template", "YTC_PROGRESS:%(progress._percent_str)s", # Custom template
        "--merge-output-format", "mp4",
        "-o", output_path,
        url
    ]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False) # text=False for byte stream
        
        return_code, stdout_lines = _process_yt_dlp_output(process, progress_callback, "cut_download")
        
        # Capture stderr after process completion
        stderr_output = ""
        if process.stderr:
            stderr_output = process.stderr.read().decode('utf-8', errors='replace')
            process.stderr.close()
            if stderr_output.strip():
                 print(f"▶ video_cutter_lib (cut_download): STDERR:\n{stderr_output}")


        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command, output="\n".join(stdout_lines), stderr=stderr_output)
        
        print(f"▶ video_cutter_lib: Video download for cut complete: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ video_cutter_lib: Video download for cut error: {e}")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
        raise
    except Exception as e:
        print(f"❌ video_cutter_lib: An unexpected error occurred during video download for cut: {e}")
        raise

def cut_video(input_path, start_time, end_time, output_path):
    """Cuts the video in the specified time range."""
    print(f"▶ video_cutter_lib: Cutting video: {input_path} [{start_time}-{end_time}] -> {output_path}")
    command = [
        "ffmpeg",
        "-y", # Overwrite output files without asking
        "-ss", start_time,
        "-to", end_time,
        "-i", input_path,
        "-c", "copy",
        output_path
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        print(f"▶ video_cutter_lib: Video cutting command output:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        print("▶ video_cutter_lib: Video cutting complete.")
    except subprocess.CalledProcessError as e:
        print(f"❌ video_cutter_lib: Video cutting error: {e}")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
        raise 
    except Exception as e:
        print(f"❌ video_cutter_lib: An unexpected error occurred during video cutting: {e}")
        raise

def download_full_video(url, full_output_path, progress_callback=None):
    """Downloads the full video from the specified URL to the given full_output_path, with progress."""
    print(f"▶ video_cutter_lib: Downloading full video: {url} -> {full_output_path}")
    
    command = [
        "yt-dlp",
        "--no-playlist",
        "--progress", # Enable progress output
        "--progress-template", "YTC_PROGRESS:%(progress._percent_str)s", # Custom template
        "--merge-output-format", "mp4", 
        "-o", full_output_path, 
        "--print", "filename", # Still print filename for confirmation
        url
    ]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
        
        return_code, stdout_lines = _process_yt_dlp_output(process, progress_callback, "full_download")

        stderr_output = ""
        if process.stderr:
            stderr_output = process.stderr.read().decode('utf-8', errors='replace')
            process.stderr.close()
            if stderr_output.strip():
                print(f"▶ video_cutter_lib (full_download): STDERR:\n{stderr_output}")

        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command, output="\n".join(stdout_lines), stderr=stderr_output)

        confirmed_output_path = None
        if stdout_lines:
            # The filename printed by --print filename should be among the last lines
            for line in reversed(stdout_lines):
                if line.strip() and os.path.exists(line.strip()): # Check if it's a valid path
                    confirmed_output_path = line.strip()
                    break
            if not confirmed_output_path: # Fallback if parsing fails, use the intended path
                 confirmed_output_path = full_output_path


        if confirmed_output_path != full_output_path and os.path.exists(full_output_path):
             # If yt-dlp saved to the requested path but printed something else (e.g. relative path)
             # and the requested path exists, prefer the requested path.
             confirmed_output_path = full_output_path
        elif confirmed_output_path != full_output_path:
            print(f"⚠️ video_cutter_lib: Confirmed output path '{confirmed_output_path}' differs from requested '{full_output_path}'. Using confirmed path if it exists, otherwise requested.")
            if not os.path.exists(confirmed_output_path): # If the printed path doesn't exist, but original does
                if os.path.exists(full_output_path):
                    confirmed_output_path = full_output_path
                else: # Neither exists, something went wrong
                     print(f"❌ video_cutter_lib: Neither confirmed path '{confirmed_output_path}' nor requested path '{full_output_path}' found.")
                     # Fallback to requested path for return, error likely already raised or will be
                     confirmed_output_path = full_output_path


        print(f"▶ video_cutter_lib: Full video download complete. Target: {full_output_path}, Confirmed/Actual: {confirmed_output_path}")
        return confirmed_output_path 
    except subprocess.CalledProcessError as e:
        print(f"❌ video_cutter_lib: Full video download error: {e}")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
        raise  
    except Exception as e:
        print(f"❌ video_cutter_lib: An unexpected error occurred during full video download: {e}")
        raise
