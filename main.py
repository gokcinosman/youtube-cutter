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
from .video_cutter_lib import download_video, cut_video

logger = logging.getLogger(__name__)

class YouTubeCutterExtension(Extension):
    def __init__(self):
        super(YouTubeCutterExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener()) # Özel eylemi işlemek için

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
        logger.info(f"Alınan sorgu: {query}")

        if not query:
            return RenderResultListAction([
                ExtensionResultItem(icon='images/icon.png',
                                    name='Kullanım: <url> <başlangıç> <bitiş>',
                                    description='Örn: https://youtu.be/xyz 00:01:00 00:02:00',
                                    on_enter=DoNothingAction())
            ])

        parts = query.split()
        if len(parts) != 3:
            return RenderResultListAction([
                ExtensionResultItem(icon='images/icon.png',
                                    name='Hatalı Girdi',
                                    description='Kullanım: <url> <başlangıç_zamanı> <bitiş_zamanı>',
                                    highlightable=False,
                                    on_enter=HideWindowAction())
            ])

        video_url, start_time, end_time = parts

        # Zaman formatını doğrula (basit kontrol)
        time_regex = re.compile(r"^\d{2}:\d{2}:\d{2}(\.\d+)?$")
        if not time_regex.match(start_time) or not time_regex.match(end_time):
            return RenderResultListAction([
                ExtensionResultItem(icon='images/icon.png',
                                    name='Hatalı Zaman Formatı',
                                    description='Zaman formatı SS:DD:SS veya SS:DD:SS.sss olmalı',
                                    highlightable=False,
                                    on_enter=HideWindowAction())
            ])
        
        # URL formatını basitçe kontrol et (daha kapsamlı kontrol eklenebilir)
        if not (video_url.startswith("http://") or video_url.startswith("https://")):
             return RenderResultListAction([
                ExtensionResultItem(icon='images/icon.png',
                                    name='Hatalı URL Formatı',
                                    description='Lütfen geçerli bir video URLsi girin.',
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
                                name=f"Videoyu Kes: {video_url}",
                                description=f"Başlangıç: {start_time}, Bitiş: {end_time}",
                                on_enter=ExtensionCustomAction(action_data, keep_app_open=False))
        ])

class ItemEnterEventListener(EventListener):
    def on_event(self, event, extension):
        data = event.get_data()
        video_url = data['url']
        start_time = data['start']
        end_time = data['end']
        
        output_directory = os.path.expanduser(extension.preferences.get('output_dir', '~/Downloads'))
        if not os.path.exists(output_directory):
            try:
                os.makedirs(output_directory)
                logger.info(f"Çıktı dizini oluşturuldu: {output_directory}")
            except OSError as e:
                logger.error(f"Çıktı dizini oluşturulamadı: {output_directory}. Hata: {e}")
                extension.show_notification("Hata", f"Çıktı dizini oluşturulamadı: {e}")
                return HideWindowAction()

        # Basit bir çıktı dosya adı oluşturma (daha sonra geliştirilebilir)
        # Örneğin video başlığını almak için yt-dlp --get-title kullanılabilir.
        # Şimdilik sabit bir isim ve zaman damgası kullanalım.
        safe_url_part = re.sub(r'[^a-zA-Z0-9]', '_', video_url.split('/')[-1]) # URL'den güvenli bir parça al
        output_filename = f"cut_{safe_url_part}_{start_time.replace(':', '')}_{end_time.replace(':', '')}.mp4"
        final_output_path = os.path.join(output_directory, output_filename)

        extension.show_notification("İşlem Başladı", f"Video indiriliyor ve kesiliyor: {video_url}")

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_video_path = os.path.join(tmpdir, "downloaded_video.mp4")
                
                logger.info(f"Geçici video dosyası: {temp_video_path}")
                extension.show_notification("İndirme", f"Video indiriliyor: {video_url}...")
                download_video(video_url, temp_video_path)
                logger.info("Video indirme tamamlandı.")
                extension.show_notification("İndirme Başarılı", "Video başarıyla indirildi.")

                logger.info(f"Video kesiliyor: {start_time} - {end_time}")
                extension.show_notification("Kesme", "Video kesiliyor...")
                cut_video(temp_video_path, start_time, end_time, final_output_path)
                logger.info("Video kesme tamamlandı.")
                
                extension.show_notification("İşlem Tamamlandı", f"Video kaydedildi: {final_output_path}")
                # İsteğe bağlı: Kaydedilen dosyayı aç
                # return OpenAction(final_output_path) 
                
        except subprocess.CalledProcessError as e:
            logger.error(f"İşlem sırasında hata: {e}")
            logger.error(f"Komut: {' '.join(e.cmd)}")
            logger.error(f"Stderr: {e.stderr}")
            extension.show_notification("Hata", f"İşlem sırasında bir hata oluştu: {e.stderr[:200]}...")
        except Exception as e:
            logger.error(f"Beklenmedik bir hata oluştu: {e}")
            extension.show_notification("Kritik Hata", f"Beklenmedik bir hata: {str(e)}")
        
        return HideWindowAction() # İşlem bittikten sonra Ulauncher'ı gizle

if __name__ == '__main__':
    YouTubeCutterExtension().run()