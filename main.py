import logging
import os
import tempfile
import subprocess
import re
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.OpenAction import OpenAction

# video_cutter_lib'den fonksiyonları import et
try:
    from .video_cutter_lib import download_video, cut_video, download_full_video
except ImportError:
    # If relative import fails, try absolute import
    try:
        from video_cutter_lib import download_video, cut_video, download_full_video
    except ImportError as e:
        logger.error(f"Could not import video_cutter_lib: {e}")
        # Define functions here (fallback)
        import subprocess
        
        def download_video(url, output_path):
            """Downloads the video from the specified URL."""
            logger.info(f"Downloading video: {url} -> {output_path}")
            command = [
                "yt-dlp",
                "--no-playlist",
                "-f", "best",
                "-o", output_path,
                url
            ]
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            logger.info("Video download complete (fallback).")

        def cut_video(input_path, start_time, end_time, output_path):
            """Cuts the video in the specified time range."""
            logger.info(f"Cutting video (fallback): {input_path} [{start_time}-{end_time}] -> {output_path}")
            command = [
                "ffmpeg",
                "-ss", start_time,
                "-to", end_time,
                "-i", input_path,
                "-c", "copy",
                output_path
            ]
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            logger.info("Video cutting complete (fallback).")

        def download_full_video(url, full_output_path): # Modified for fallback
            """Downloads the full video from the specified URL to the output_dir (fallback)."""
            logger.info(f"Downloading full video (fallback): {url} -> {full_output_path}")
            # This fallback is simplified and won't return the exact filename like the main one.
            # It also doesn't use --print filename.
            command = [
                "yt-dlp",
                "--no-playlist",
                "--merge-output-format", "mp4",
                "-o", full_output_path, # Use full path for output
                url
            ]
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            logger.info("Full video download complete (fallback).")
            # In a real fallback, determining the exact output filename would be complex here.
            # For simplicity, we won't return it, main.py's fallback handling would need to be aware.
            return full_output_path # Assume success and return requested path

logger = logging.getLogger(__name__)

def get_next_available_filename(directory, file_extension="mp4"):
    """
    Finds the next available sequential filename (1.ext, 2.ext, etc.) in the given directory.
    """
    i = 1
    while True:
        filename = f"{i}.{file_extension}"
        filepath = os.path.join(directory, filename)
        if not os.path.exists(filepath):
            return filepath
        i += 1

def parse_flexible_time(time_str):
    """
    Parses a flexible time string (e.g., "1h2m3s", "10m", "30s")
    and converts it to HH:MM:SS format.
    Returns None if parsing fails.
    """
    if not time_str:
        return None

    hours = 0
    minutes = 0
    seconds = 0
    
    h_match = re.search(r"(\d+)h", time_str)
    if h_match:
        hours = int(h_match.group(1))
        time_str = time_str.replace(h_match.group(0), "") 

    m_match = re.search(r"(\d+)m", time_str)
    if m_match:
        minutes = int(m_match.group(1))
        time_str = time_str.replace(m_match.group(0), "")

    s_match = re.search(r"(\d+)s", time_str)
    if s_match:
        seconds = int(s_match.group(1))
        time_str = time_str.replace(s_match.group(0), "")

    if time_str.strip(): 
        if time_str.strip().isdigit() and not (h_match or m_match or s_match): 
             seconds = int(time_str.strip())
        elif time_str.strip().isdigit() and not s_match: 
            seconds = int(time_str.strip())
        elif time_str.strip() != "": 
            logger.warning(f"Invalid characters in time string: {time_str}")
            return None

    if hours == 0 and minutes == 0 and seconds == 0 and not (h_match or m_match or s_match or time_str.strip().isdigit()):
        return None

    minutes += seconds // 60
    seconds %= 60
    hours += minutes // 60
    minutes %= 60

    if hours > 99: 
        logger.warning(f"Hours exceed 99: {hours}")
        return None

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class YouTubeCutterExtension(Extension):
    def __init__(self):
        super(YouTubeCutterExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener()) 

    def show_notification(self, title, text, notification_type="info"):
        try:
            subprocess.run([
                'notify-send', 
                '-a', 'YouTube Cutter',
                '-i', 'video-x-generic', 
                title, 
                text
            ], check=False) 
        except Exception as e:
            logger.warning(f"Could not show notification: {e}")

class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        query = event.get_argument() or ""
        logger.info(f"Received query: {query}")

        if not query:
            return RenderResultListAction([
                ExtensionResultItem(icon='images/icon.png',
                                    name='Usage: <url> <start> <end> OR <url> full',
                                    description='Time: 1m30s, 2h, 45s. Ex: ... 1m30s 2m15s OR ... full',
                                    on_enter=DoNothingAction())
            ])

        parts = query.split()
        
        action_data = {}
        item_name = ""
        item_description = ""

        if len(parts) == 3: 
            video_url, start_time_str, end_time_str = parts
            start_time = parse_flexible_time(start_time_str)
            end_time = parse_flexible_time(end_time_str)

            if start_time is None or end_time is None:
                return RenderResultListAction([
                    ExtensionResultItem(icon='images/icon.png',
                                        name='Invalid Time Format for Cut',
                                        description='Use format like 1h2m3s, 10m, 30s, or HH:MM:SS.',
                                        highlightable=False,
                                        on_enter=HideWindowAction())
                ])
            if not (video_url.startswith("http://") or video_url.startswith("https://")):
                return RenderResultListAction([
                    ExtensionResultItem(icon='images/icon.png',
                                        name='Invalid URL Format',
                                        description='Please enter a valid video URL.',
                                        highlightable=False,
                                        on_enter=HideWindowAction())
                ])
            
            action_data = {'action_type': 'cut', 'url': video_url, 'start': start_time, 'end': end_time}
            item_name = f"Cut Video: {video_url}"
            item_description = f"Start: {start_time}, End: {end_time}"

        elif len(parts) == 2 and parts[1].lower() == 'full': 
            video_url = parts[0]
            if not (video_url.startswith("http://") or video_url.startswith("https://")):
                return RenderResultListAction([
                    ExtensionResultItem(icon='images/icon.png',
                                        name='Invalid URL Format',
                                        description='Please enter a valid video URL.',
                                        highlightable=False,
                                        on_enter=HideWindowAction())
                ])

            action_data = {'action_type': 'full_download', 'url': video_url}
            item_name = f"Download Full Video: {video_url}"
            item_description = "Download the entire video. Filename will be sequential (e.g., 1.mp4)."

        else: 
            return RenderResultListAction([
                ExtensionResultItem(icon='images/icon.png',
                                    name='Invalid Input Format',
                                    description='Use: <url> <start> <end> OR <url> full',
                                    highlightable=False,
                                    on_enter=HideWindowAction())
            ])

        return RenderResultListAction([
            ExtensionResultItem(icon='images/icon.png',
                                name=item_name,
                                description=item_description,
                                on_enter=ExtensionCustomAction(action_data, keep_app_open=False))
        ])

class ItemEnterEventListener(EventListener):
    def on_event(self, event, extension):
        data = event.get_data()
        action_type = data.get('action_type')
        video_url = data['url']
        
        output_directory = os.path.expanduser(extension.preferences.get('ytc_output_dir', '~/Downloads'))
        if not os.path.exists(output_directory):
            try:
                os.makedirs(output_directory)
                logger.info(f"Output directory created: {output_directory}")
            except OSError as e:
                logger.error(f"Could not create output directory: {output_directory}. Error: {e}")
                extension.show_notification("Error", f"Could not create output directory: {e}")
                return HideWindowAction()
        
        final_output_path = get_next_available_filename(output_directory, "mp4")

        try:
            if action_type == 'cut':
                start_time = data['start']
                end_time = data['end']
                
                extension.show_notification("Processing Started", f"Downloading and cutting video: {video_url}")
                with tempfile.TemporaryDirectory() as tmpdir:
                    temp_video_path = os.path.join(tmpdir, "downloaded_video.mp4")
                    
                    logger.info(f"Temporary video file for cutting: {temp_video_path}")
                    extension.show_notification("Download (for cut)", f"Downloading video: {video_url}...")
                    download_video(video_url, temp_video_path) 
                    logger.info("Video download for cut complete.")
                    extension.show_notification("Download Successful (for cut)", "Video downloaded.")

                    logger.info(f"Cutting video: {start_time} - {end_time} to {final_output_path}")
                    extension.show_notification("Cutting", "Cutting video...")
                    cut_video(temp_video_path, start_time, end_time, final_output_path)
                    logger.info("Video cutting complete.")
                    extension.show_notification("Processing Complete", f"Cut video saved: {final_output_path}")

            elif action_type == 'full_download':
                extension.show_notification("Processing Started", f"Downloading full video: {video_url}")
                
                confirmed_download_path = download_full_video(video_url, final_output_path)
                
                if confirmed_download_path and os.path.exists(confirmed_download_path):
                    logger.info(f"Full video download complete: {confirmed_download_path}")
                    extension.show_notification("Download Complete", f"Full video saved: {confirmed_download_path}")
                else:
                    logger.error(f"Full video download attempted to {final_output_path}, but path confirmation failed or file not found. Confirmed path: {confirmed_download_path}")
                    extension.show_notification("Download Issue", f"Full video download to {final_output_path} may have failed. Please check the directory.")

            else:
                logger.error(f"Unknown action type: {action_type}")
                extension.show_notification("Error", "Unknown action requested.")
                return HideWindowAction()

            if extension.preferences.get('ytc_auto_open_dir') is True:
                logger.info(f"Auto-opening output directory: {output_directory}")
                return OpenAction(output_directory)
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Error during processing: {e}")
            logger.error(f"Command: {' '.join(e.cmd)}")
            logger.error(f"Stderr: {e.stderr}")
            extension.show_notification("Error", f"An error occurred during processing: {e.stderr[:200]}...")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            extension.show_notification("Critical Error", f"Unexpected error: {str(e)}")
        
        return HideWindowAction() 

if __name__ == '__main__':
    YouTubeCutterExtension().run()
