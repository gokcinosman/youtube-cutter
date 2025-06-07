import logging
import os
import tempfile
import subprocess
import re
import time 
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.OpenAction import OpenAction

try:
    from .video_cutter_lib import download_video, cut_video, download_full_video
except ImportError:
    try:
        from video_cutter_lib import download_video, cut_video, download_full_video
    except ImportError as e:
        logger = logging.getLogger(__name__) # Ensure logger is defined before use
        logger.error(f"Could not import video_cutter_lib: {e}")
        import subprocess
        def download_video(url, output_path, progress_callback=None):
            logger.info(f"Downloading video (fallback): {url} -> {output_path}")
            subprocess.run(["yt-dlp", "--no-playlist", "-f", "best", "-o", output_path, url], check=True)
            if progress_callback: progress_callback("100%")
        def cut_video(input_path, start_time, end_time, output_path):
            logger.info(f"Cutting video (fallback): {input_path} [{start_time}-{end_time}] -> {output_path}")
            subprocess.run(["ffmpeg", "-ss", start_time, "-to", end_time, "-i", input_path, "-c", "copy", output_path], check=True)
        def download_full_video(url, full_output_path, progress_callback=None):
            logger.info(f"Downloading full video (fallback): {url} -> {full_output_path}")
            subprocess.run(["yt-dlp", "--no-playlist", "--merge-output-format", "mp4", "-o", full_output_path, url], check=True)
            if progress_callback: progress_callback("100%")
            return full_output_path

logger = logging.getLogger(__name__)

def get_next_available_filename(directory, file_extension="mp4"):
    i = 1
    while True:
        filename = f"{i}.{file_extension}"
        filepath = os.path.join(directory, filename)
        if not os.path.exists(filepath): return filepath
        i += 1

def parse_flexible_time(time_str):
    if not time_str: return None
    hours, minutes, seconds = 0, 0, 0
    h_match = re.search(r"(\d+)h", time_str); 
    if h_match: hours = int(h_match.group(1)); time_str = time_str.replace(h_match.group(0), "")
    m_match = re.search(r"(\d+)m", time_str); 
    if m_match: minutes = int(m_match.group(1)); time_str = time_str.replace(m_match.group(0), "")
    s_match = re.search(r"(\d+)s", time_str); 
    if s_match: seconds = int(s_match.group(1)); time_str = time_str.replace(s_match.group(0), "")
    if time_str.strip():
        if time_str.strip().isdigit() and not (h_match or m_match or s_match): seconds = int(time_str.strip())
        elif time_str.strip().isdigit() and not s_match: seconds = int(time_str.strip())
        elif time_str.strip() != "": logger.warning(f"Invalid chars in time: {time_str}"); return None
    if hours==0 and minutes==0 and seconds==0 and not (h_match or m_match or s_match or time_str.strip().isdigit()): return None
    minutes += seconds // 60; seconds %= 60; hours += minutes // 60; minutes %= 60
    if hours > 99: logger.warning(f"Hours > 99: {hours}"); return None
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

class YouTubeCutterExtension(Extension):
    def __init__(self):
        super(YouTubeCutterExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener()) 

    def show_notification(self, title, text, notification_type="info"):
        try:
            subprocess.run(['notify-send', '-a', 'YouTube Cutter', '-i', 'video-x-generic', title, text], check=False) 
        except Exception as e:
            logger.warning(f"Could not show notification: {e}")

class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        query = event.get_argument() or ""
        if not query:
            return RenderResultListAction([ExtensionResultItem(icon='images/icon.png', name='Usage: <url> <start> <end> OR <url> full', description='Time: 1m30s, 2h, 45s. Ex: ... 1m30s 2m15s OR ... full', on_enter=DoNothingAction())])
        parts = query.split()
        action_data, item_name, item_description = {}, "", ""
        if len(parts) == 3: 
            video_url, start_time_str, end_time_str = parts
            start_time, end_time = parse_flexible_time(start_time_str), parse_flexible_time(end_time_str)
            if start_time is None or end_time is None: return RenderResultListAction([ExtensionResultItem(icon='images/icon.png', name='Invalid Time Format for Cut', description='Use format like 1h2m3s, 10m, 30s, or HH:MM:SS.', highlightable=False, on_enter=HideWindowAction())])
            if not (video_url.startswith("http://") or video_url.startswith("https://")): return RenderResultListAction([ExtensionResultItem(icon='images/icon.png', name='Invalid URL Format', description='Please enter a valid video URL.', highlightable=False, on_enter=HideWindowAction())])
            action_data = {'action_type': 'cut', 'url': video_url, 'start': start_time, 'end': end_time}; item_name = f"Cut Video: {video_url}"; item_description = f"Start: {start_time}, End: {end_time}"
        elif len(parts) == 2 and parts[1].lower() == 'full': 
            video_url = parts[0]
            if not (video_url.startswith("http://") or video_url.startswith("https://")): return RenderResultListAction([ExtensionResultItem(icon='images/icon.png', name='Invalid URL Format', description='Please enter a valid video URL.', highlightable=False, on_enter=HideWindowAction())])
            action_data = {'action_type': 'full_download', 'url': video_url}; item_name = f"Download Full Video: {video_url}"; item_description = "Download the entire video. Filename will be sequential (e.g., 1.mp4)."
        else: return RenderResultListAction([ExtensionResultItem(icon='images/icon.png', name='Invalid Input Format', description='Use: <url> <start> <end> OR <url> full', highlightable=False, on_enter=HideWindowAction())])
        return RenderResultListAction([ExtensionResultItem(icon='images/icon.png', name=item_name, description=item_description, on_enter=ExtensionCustomAction(action_data, keep_app_open=False))])

class ItemEnterEventListener(EventListener):
    def __init__(self):
        super(ItemEnterEventListener, self).__init__()
        self.last_notification_time = 0
        self.last_reported_percentage_str = "" # Store the string to avoid re-notifying same string

    def _progress_callback(self, extension, percentage_str, operation_name="Download"):
        try:
            notify_interval_str = extension.preferences.get('ytc_progress_notify_interval', "5")
            try:
                notify_interval = int(notify_interval_str)
            except ValueError:
                logger.warning(f"Invalid progress notification interval: '{notify_interval_str}'. Defaulting to 5 seconds.")
                notify_interval = 5

            current_time = time.time()
            is_final = "100" in percentage_str # A bit simplistic, but good for final update

            # Avoid sending the exact same percentage string repeatedly if yt-dlp sends it multiple times
            if percentage_str == self.last_reported_percentage_str and not is_final:
                return

            if is_final or notify_interval == 0 or (current_time - self.last_notification_time >= notify_interval) :
                extension.show_notification(f"{operation_name} Progress", f"{percentage_str.strip()}")
                self.last_notification_time = current_time
                self.last_reported_percentage_str = percentage_str
            
            if is_final: # Reset for next operation
                self.last_notification_time = 0
                self.last_reported_percentage_str = ""


        except Exception as e: # Catch any error within callback to prevent crashing the main thread
            logger.error(f"Error in progress_callback: {e}", exc_info=True)
            # Show it anyway if an error occurs, but don't update time to allow next one sooner
            extension.show_notification(f"{operation_name} Progress", f"{percentage_str.strip()} (callback error)")


    def on_event(self, event, extension):
        self.last_notification_time = 0 # Reset for each new operation
        self.last_reported_percentage_str = ""

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
                    
                    download_video(video_url, temp_video_path, 
                                   lambda p: self._progress_callback(extension, p, "Download (for cut)")) 
                    
                    logger.info("Video download for cut complete.")
                    # Notification for "Download Successful" is now handled by 100% progress or final callback state

                    logger.info(f"Cutting video: {start_time} - {end_time} to {final_output_path}")
                    extension.show_notification("Cutting", "Cutting video...")
                    cut_video(temp_video_path, start_time, end_time, final_output_path)
                    logger.info("Video cutting complete.")
                    extension.show_notification("Processing Complete", f"Cut video saved: {final_output_path}")

            elif action_type == 'full_download':
                extension.show_notification("Processing Started", f"Downloading full video: {video_url}")
                
                confirmed_download_path = download_full_video(video_url, final_output_path,
                                                              lambda p: self._progress_callback(extension, p, "Full Download"))
                
                # Notification for "Download Complete" is now handled by 100% progress or final callback state
                if confirmed_download_path and os.path.exists(confirmed_download_path):
                    logger.info(f"Full video download complete: {confirmed_download_path}")
                    # No separate "Download Complete" notification here if 100% progress already sent it
                else:
                    logger.error(f"Full video download attempted to {final_output_path}, but path confirmation failed or file not found. Confirmed path: {confirmed_download_path}")
                    extension.show_notification("Download Issue", f"Full video download to {final_output_path} may have failed. Please check the directory.")

            else:
                logger.error(f"Unknown action type: {action_type}")
                extension.show_notification("Error", "Unknown action requested.")
                return HideWindowAction()

            auto_open_pref = extension.preferences.get('ytc_auto_open_dir', "true")
            if auto_open_pref == "true": # Compare with string "true"
                logger.info(f"Auto-opening output directory: {output_directory}")
                return OpenAction(output_directory)
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Error during processing: {e}")
            cmd_str = ' '.join(e.cmd if isinstance(e.cmd, list) else [str(e.cmd)])
            stderr_str = e.stderr[:200] if e.stderr else str(e)
            logger.error(f"Command: {cmd_str}")
            logger.error(f"Stderr: {stderr_str}")
            extension.show_notification("Error", f"An error occurred: {stderr_str}...")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            extension.show_notification("Critical Error", f"Unexpected error: {str(e)}")
        
        return HideWindowAction() 

if __name__ == '__main__':
    YouTubeCutterExtension().run()
