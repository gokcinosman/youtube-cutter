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
    from .video_cutter_lib import download_video, cut_video
except ImportError:
    # If relative import fails, try absolute import
    try:
        from video_cutter_lib import download_video, cut_video
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
                                    name='Usage: <url> <start_time> <end_time>',
                                    description='Time format: e.g., 1m30s, 2h5m, 45s. Ex: https://youtu.be/xyz 1m30s 2m15s',
                                    on_enter=DoNothingAction())
            ])

        parts = query.split()
        if len(parts) != 3:
            return RenderResultListAction([
                ExtensionResultItem(icon='images/icon.png',
                                    name='Invalid Input',
                                    description='Usage: <url> <start_time> <end_time>. Time: e.g., 1m30s, 2h, 45s',
                                    highlightable=False,
                                    on_enter=HideWindowAction())
            ])

        video_url, start_time_str, end_time_str = parts

        start_time = parse_flexible_time(start_time_str)
        end_time = parse_flexible_time(end_time_str)

        if start_time is None or end_time is None:
            return RenderResultListAction([
                ExtensionResultItem(icon='images/icon.png',
                                    name='Invalid Time Format',
                                    description='Use format like 1h2m3s, 10m, 30s, or HH:MM:SS.',
                                    highlightable=False,
                                    on_enter=HideWindowAction())
            ])
        
        # Simple URL format check (more comprehensive check can be added)
        if not (video_url.startswith("http://") or video_url.startswith("https://")):
             return RenderResultListAction([
                ExtensionResultItem(icon='images/icon.png',
                                    name='Invalid URL Format',
                                    description='Please enter a valid video URL.',
                                    highlightable=False,
                                    on_enter=HideWindowAction())
            ])

        action_data = {
            'url': video_url,
            'start': start_time,
            'end': end_time
        }

        return RenderResultListAction([
            ExtensionResultItem(icon='images/icon.png',
                                name=f"Cut Video: {video_url}",
                                description=f"Start: {start_time}, End: {end_time}",
                                on_enter=ExtensionCustomAction(action_data, keep_app_open=False))
        ])

class ItemEnterEventListener(EventListener):
    def on_event(self, event, extension):
        data = event.get_data()
        video_url = data['url']
        start_time = data['start']
        end_time = data['end']
        
        output_directory = os.path.expanduser(extension.preferences.get('ytc_output_dir', '~/Downloads')) # Use correct preference ID
        if not os.path.exists(output_directory):
            try:
                os.makedirs(output_directory)
                logger.info(f"Output directory created: {output_directory}")
            except OSError as e:
                logger.error(f"Could not create output directory: {output_directory}. Error: {e}")
                extension.show_notification("Error", f"Could not create output directory: {e}")
                return HideWindowAction()

        # Simple output filename generation (can be improved later)
        # For example, yt-dlp --get-title could be used to get the video title.
        # For now, let's use a fixed name and timestamp.
        safe_url_part = re.sub(r'[^a-zA-Z0-9]', '_', video_url.split('/')[-1]) # Get a safe part from URL
        output_filename = f"cut_{safe_url_part}_{start_time.replace(':', '')}_{end_time.replace(':', '')}.mp4"
        final_output_path = os.path.join(output_directory, output_filename)

        extension.show_notification("Processing Started", f"Downloading and cutting video: {video_url}")

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_video_path = os.path.join(tmpdir, "downloaded_video.mp4")
                
                logger.info(f"Temporary video file: {temp_video_path}")
                extension.show_notification("Download", f"Downloading video: {video_url}...")
                download_video(video_url, temp_video_path)
                logger.info("Video download complete.")
                extension.show_notification("Download Successful", "Video downloaded successfully.")

                logger.info(f"Cutting video: {start_time} - {end_time}")
                extension.show_notification("Cutting", "Cutting video...")
                cut_video(temp_video_path, start_time, end_time, final_output_path)
                logger.info("Video cutting complete.")
                
                extension.show_notification("Processing Complete", f"Video saved: {final_output_path}")
                # Optional: Open the saved file
                # return OpenAction(final_output_path) 
                
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
