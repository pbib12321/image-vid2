import os
import requests
import threading
import itertools
import time
import zipfile
import shutil
from flask import Flask, request, send_file, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote
import yt_dlp

app = Flask(__name__)

# Thread-safe counters and sets
lock = threading.Lock()

# ---------------- Helper Functions ----------------
def download_images(search_word, max_images=10):
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    folder = os.path.join(desktop, f"{search_word}_google")
    os.makedirs(folder, exist_ok=True)
    
    downloaded_image_urls = set()
    counter_images = itertools.count(1)
    
    BASE_URL = "https://www.google.com/search?q={word}&tbm=isch&safe=off&start={start}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    start = 0
    
    while len(downloaded_image_urls) < max_images:
        try:
            url = BASE_URL.format(word=search_word, start=start)
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                start += 20
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            images = soup.find_all("img")
            for img in images:
                src = img.get("src")
                if not src or not src.startswith("http"):
                    continue
                if src in downloaded_image_urls:
                    continue
                downloaded_image_urls.add(src)
                img_num = next(counter_images)
                file_path = os.path.join(folder, f"{search_word}_img_{img_num}.jpg")
                try:
                    img_data = requests.get(src, headers=headers, timeout=10).content
                    with open(file_path, "wb") as f:
                        f.write(img_data)
                    if len(downloaded_image_urls) >= max_images:
                        break
                except:
                    continue
            start += 20
        except:
            start += 20
            continue
    return folder

def download_video(link, folder):
    try:
        ydl_opts = {
            'outtmpl': os.path.join(folder, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'format': 'mp4[height<=480]',
            'nocheckcertificate': True,
            'geo_bypass': True,
            'socket_timeout': 15,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/115.0.0.0 Safari/537.36'
            },
            'retries': 3,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])
        return True
    except Exception as e:
        print(f"[Video] Failed to download {link}: {e}")
        return False

def download_videos(search_word, max_videos=5):
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    folder = os.path.join(desktop, f"{search_word}_google")
    os.makedirs(folder, exist_ok=True)
    
    downloaded_video_urls = set()
    BASE_URL = "https://www.google.com/search?q={word}&tbm=vid&safe=off&start={start}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    start = 0
    downloaded_count = 0
    
    while downloaded_count < max_videos:
        try:
            url = BASE_URL.format(word=search_word, start=start)
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                start += 10
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            video_links = []
            for a in soup.find_all("a"):
                href = a.get("href")
                if href and href.startswith("/url?q="):
                    parsed = parse_qs(urlparse(href).query)
                    if "q" in parsed:
                        real_url = unquote(parsed["q"][0])
                        if real_url not in downloaded_video_urls:
                            video_links.append(real_url)
            if not video_links:
                start += 10
                continue
            for link in video_links:
                downloaded_video_urls.add(link)
                success = download_video(link, folder)
                if not success:
                    return folder, False
                downloaded_count += 1
                if downloaded_count >= max_videos:
                    break
            start += 10
        except:
            start += 10
            continue
    return folder, True

def make_zip(folder_path, zip_name):
    zip_path = f"{folder_path}.zip"
    shutil.make_archive(folder_path, 'zip', folder_path)
    return zip_path

# ---------------- Flask Routes ----------------
@app.route('/download', methods=['POST'])
def download_route():
    data = request.get_json()
    search_word = data.get('search_word', '').strip()
    mode = data.get('mode', 'images')
    
    if not search_word:
        return jsonify({'error': 'No search keyword provided.'}), 400
    
    try:
        final_folder = None
        success = True
        if mode == 'images':
            final_folder = download_images(search_word)
        elif mode == 'videos':
            final_folder, success = download_videos(search_word)
        elif mode == 'both':
            download_images(search_word)
            final_folder, success = download_videos(search_word)
        else:
            return jsonify({'error': 'Invalid mode.'}), 400
        
        zip_path = make_zip(final_folder, f"{search_word}_{mode}")
        if not success:
            return jsonify({'error': 'Could not download videos properly.'}), 500
        
        return send_file(zip_path, mimetype='application/zip', as_attachment=True,
                         download_name=f"{search_word}_{mode}.zip")
    except Exception as e:
        print(e)
        return jsonify({'error': 'Server error.'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
