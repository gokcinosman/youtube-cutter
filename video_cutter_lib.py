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
            # print(f"▶ video_cutter_lib ({action_name}): STDOUT line: {line}") # Verbose logging
            
            if progress_callback:
                # Try to match a line that is primarily a percentage, possibly with whitespace
                # This assumes the --progress-template is outputting just the percentage string.
                # Example: "  10.5%"
                match = re.fullmatch(r"\s*([\d\.]+\s*%)\s*", line) # Match full line as percentage
                if match:
                    percentage = match.group(1).strip()
                    progress_callback(percentage)
                # Keep the old fallback just in case, though it might be less likely to hit with the new template
                elif "[download]" in line: # Check if it's a standard yt-dlp download line
                    match_default = re.search(r"\[download\]\s+([\d\.]+%)", line)
                    if match_default:
                        percentage = match_default.group(1).strip()
                        progress_callback(percentage)
        process.stdout.close()
    
    process.wait() 
    return process.returncode, all_stdout_lines

def download_video(url, output_path, progress_callback=None):
    """Downloads the video from the specified URL, with progress reporting."""
    print(f"▶ video_cutter_lib: Downloading video for cut: {url} -> {output_path}")
    command = [
        "yt-dlp",
        "--no-playlist",
        "--progress", 
        "--newline", # Force progress on new lines
        "--progress-template", "%(progress._percent_str)s", # Simplest percentage template
        "--merge-output-format", "mp4",
        "-o", output_path,
        url
    ]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
        return_code, stdout_lines = _process_yt_dlp_output(process, progress_callback, "cut_download")
        
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
        "-y", 
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
        "--progress",
        "--newline", # Force progress on new lines
        "--progress-template", "%(progress._percent_str)s", # Simplest percentage template
        "--merge-output-format", "mp4", 
        "-o", full_output_path, 
        "--print", "filename", 
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
        # Try to find the filename from --print filename, which might be mixed with progress lines
        # It's often one of the last non-empty lines that is also a valid file path.
        for line in reversed(stdout_lines):
            potential_path = line.strip()
            if potential_path and os.path.exists(potential_path) and potential_path.endswith(".mp4"): # Basic check
                confirmed_output_path = potential_path
                break
        
        if not confirmed_output_path: # If not found, assume it's the requested path
            confirmed_output_path = full_output_path
            if not os.path.exists(confirmed_output_path): # If still not found, then there's an issue
                 print(f"❌ video_cutter_lib: Output file {full_output_path} not found after download.")
                 # No specific error to raise here if yt-dlp exited 0, main.py will handle file check.

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
