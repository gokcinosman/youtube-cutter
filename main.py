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

        def download_full_video(url, output_dir):
            """Downloads the full video from the specified URL to the output_dir (fallback)."""
            logger.info(f"Downloading full video (fallback): {url} -> {output_dir}")
            # This fallback is simplified and won't return the exact filename like the main one.
            # It also doesn't use --print filename.
            command = [
                "yt-dlp",
                "--no-playlist",
                "--merge-output-format", "mp4",
                "-P", output_dir,
                # "-o", "%(title)s.%(ext)s", # Implicit with -P
                url
            ]
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            logger.info("Full video download complete (fallback).")
            # In a real fallback, determining the exact output filename would be complex here.
            # For simplicity, we won't return it, main.py's fallback handling would need to be aware.
            return None # Fallback cannot easily determine the filename

logger = logging.getLogger(__name__)

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

    # Regex to capture h, m, s components
    # Allows for optional components and various orderings, but we'll process them sequentially
    # For simplicity, we'll assume a common pattern like XhYmZs or just YmZs or Zs etc.
    # A more robust parser might handle any order, but this should cover most cases.
    
    h_match = re.search(r"(\d+)h", time_str)
    if h_match:
        hours = int(h_match.group(1))
        time_str = time_str.replace(h_match.group(0), "") # Remove matched part

    m_match = re.search(r"(\d+)m", time_str)
    if m_match:
        minutes = int(m_match.group(1))
        time_str = time_str.replace(m_match.group(0), "")

    s_match = re.search(r"(\d+)s", time_str)
    if s_match:
        seconds = int(s_match.group(1))
        time_str = time_str.replace(s_match.group(0), "")

    # If there's any leftover string that isn't h, m, or s, it's an invalid format
    if time_str.strip(): # Check if anything remains after removing h, m, s parts
        # Check if the remainder is just a number, implying seconds if no unit was given
        if time_str.strip().isdigit() and not (h_match or m_match or s_match): # Only if no other units were found
             seconds = int(time_str.strip())
        elif time_str.strip().isdigit() and not s_match: # If only h or m were found, last number is seconds
            seconds = int(time_str.strip())
        elif time_str.strip() != "": # If there's non-numeric leftover, it's an error
            logger.warning(f"Invalid characters in time string: {time_str}")
            return None


    if hours == 0 and minutes == 0 and seconds == 0 and not (h_match or m_match or s_match or time_str.strip().isdigit()):
        # If input was like "abc" and not numbers or h/m/s units
        return None

    # Convert to HH:MM:SS
    # Handle potential overflows from seconds/minutes if user enters e.g. 90s
    minutes += seconds // 60
    seconds %= 60
    hours += minutes // 60
    minutes %= 60

    if hours > 99: # Arbitrary limit for hours
        logger.warning(f"Hours exceed 99: {hours}")
        return None

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class YouTubeCutterExtension(Extension):
    def __init__(self):
        super(YouTubeCutterExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener()) # To handle custom action

    def show_notification(self, title, text, notification_type="info"):
        """
        Show notification using system notification system
        Since Ulauncher doesn't have built-in notification API in older versions,
        we'll use system notifications via subprocess
        """
        try:
            # Use notify-send for Linux desktop notifications
            subprocess.run([
                'notify-send', 
                '-a', 'YouTube Cutter',
                '-i', 'video-x-generic',  # Generic video icon
                title, 
                text
            ], check=False)  # Don't raise exception if notify-send fails
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

        if len(parts) == 3: # Cut video: <url> <start_time> <end_time>
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

        elif len(parts) == 2 and parts[1].lower() == 'full': # Download full video: <url> full
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
            item_description = "Download the entire video using its title as filename."

        else: # Invalid format
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

        try:
            if action_type == 'cut':
                start_time = data['start']
                end_time = data['end']
                
                safe_url_part = re.sub(r'[^a-zA-Z0-9]', '_', video_url.split('/')[-1])
                output_filename = f"cut_{safe_url_part}_{start_time.replace(':', '')}_{end_time.replace(':', '')}.mp4"
                final_output_path = os.path.join(output_directory, output_filename)

                extension.show_notification("Processing Started", f"Downloading and cutting video: {video_url}")
                with tempfile.TemporaryDirectory() as tmpdir:
                    temp_video_path = os.path.join(tmpdir, "downloaded_video.mp4")
                    
                    logger.info(f"Temporary video file for cutting: {temp_video_path}")
                    extension.show_notification("Download (for cut)", f"Downloading video: {video_url}...")
                    download_video(video_url, temp_video_path) # This is the partial download for cutting
                    logger.info("Video download for cut complete.")
                    extension.show_notification("Download Successful (for cut)", "Video downloaded.")

                    logger.info(f"Cutting video: {start_time} - {end_time}")
                    extension.show_notification("Cutting", "Cutting video...")
                    cut_video(temp_video_path, start_time, end_time, final_output_path)
                    logger.info("Video cutting complete.")
                    extension.show_notification("Processing Complete", f"Cut video saved: {final_output_path}")

            elif action_type == 'full_download':
                extension.show_notification("Processing Started", f"Downloading full video: {video_url}")
                
                # The download_full_video function saves directly to output_directory and returns the full path
                downloaded_file_full_path = download_full_video(video_url, output_directory)
                
                if downloaded_file_full_path:
                    logger.info(f"Full video download complete: {downloaded_file_full_path}")
                    extension.show_notification("Download Complete", f"Full video saved: {downloaded_file_full_path}")
                else:
                    # This case might happen if the fallback download_full_video was used and couldn't return filename
                    logger.warning("Full video downloaded, but exact path not returned by library (possibly fallback).")
                    extension.show_notification("Download Complete", f"Full video downloaded to {output_directory}. Filename determined by video title.")


            else:
                logger.error(f"Unknown action type: {action_type}")
                extension.show_notification("Error", "Unknown action requested.")
                return HideWindowAction()

            # Open the output directory if the preference is set, after either action
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
        
        return HideWindowAction() # Hide Ulauncher after processing

if __name__ == '__main__':
    YouTubeCutterExtension().run()
