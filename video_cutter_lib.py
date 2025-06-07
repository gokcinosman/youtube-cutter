import subprocess
import os
# import tempfile # Bu artık main.py'de yönetilecek
# import shutil # Bu artık main.py'de yönetilecek

def download_video(url, output_path):
    """Videoyu belirtilen URL'den indirir."""
    print(f"▶ video_cutter_lib: Videoyu indiriyor: {url} -> {output_path}")
    command = [
        "yt-dlp",
        "--no-playlist",
        # "-f", "best", # Removed as per yt-dlp suggestion
        "--merge-output-format", "mp4",
        "-o", output_path,
        url
    ]
    try:
        # Hata durumunda CalledProcessError fırlatır.
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"▶ video_cutter_lib: Video indirme komutu çıktısı:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        print("▶ video_cutter_lib: Video indirme tamamlandı.")
    except subprocess.CalledProcessError as e:
        print(f"❌ video_cutter_lib: Video indirme hatası: {e}")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
        raise  # Hatanın yukarıya (main.py'ye) iletilmesi için

def cut_video(input_path, start_time, end_time, output_path):
    """Videoyu belirtilen zaman aralığında keser."""
    print(f"▶ video_cutter_lib: Videoyu kesiyor: {input_path} [{start_time}-{end_time}] -> {output_path}")
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
        print(f"▶ video_cutter_lib: Video kesme komutu çıktısı:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        print("▶ video_cutter_lib: Video kesme tamamlandı.")
    except subprocess.CalledProcessError as e:
        print(f"❌ video_cutter_lib: Video kesme hatası: {e}")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
        raise # Hatanın yukarıya (main.py'ye) iletilmesi için

# main() fonksiyonu ve if __name__ == "__main__": bloğu kaldırıldı.
# tempfile.TemporaryDirectory() ve output_video yolu yönetimi ana eklenti (main.py) tarafında yapılacak.
