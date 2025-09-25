import os
import io
import requests
import threading
import itertools
import zipfile
import time
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote
from flask import Flask, request, send_file, jsonify
import yt_dlp

app = Flask(__name__)
lock = threading.Lock()

def google_image_worker(search_word, folder, downloaded_image_urls):
    BASE_URL = "https://www.google.com/search?q={word}&tbm=isch&safe=off&start={start}"
    start = 0
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    counter_images = itertools.count(1)
    while start < 60:
        try:
            url = BASE_URL.format(word=search_word, start=start)
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                time.sleep(5)
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            images = soup.find_all("img")
            new_found = False
            for img in images:
                src = img.get("src")
                if not src or not src.startswith("http"):
                    continue
                with lock:
                    if src in downloaded_image_urls:
                        continue
                    downloaded_image_urls.add(src)
                img_num = next(counter_images)
                file_path = os.path.join(folder, f"{search_word}_img_{img_num}.jpg")
                try:
                    img_data = requests.get(src, headers=headers, timeout=10).content
                    with open(file_path, "wb") as f:
                        f.write(img_data)
                    new_found = True
                except:
                    continue
            if not new_found:
                start += 20
            else:
                time.sleep(1)
        except:
            time.sleep(5)

def google_video_worker(search_word, folder, downloaded_video_urls):
    BASE_URL = "https://www.google.com/search?q={word}&tbm=vid&safe=off&start={start}"
    start = 0
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    while start < 30:
        try:
            url = BASE_URL.format(word=search_word, start=start)
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                time.sleep(5)
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            video_links = []
            for a in soup.find_all("a"):
                href = a.get("href")
                if href and href.startswith("/url?q="):
                    parsed = parse_qs(urlparse(href).query)
                    if "q" in parsed:
                        real_url = unquote(parsed["q"][0])
                        video_links.append(real_url)
            if not video_links:
                start += 10
                continue
            for link in video_links:
                with lock:
                    if link in downloaded_video_urls:
                        continue
                    downloaded_video_urls.add(link)
                download_video(link, folder)
            start += 10
            time.sleep(1)
        except:
            time.sleep(5)

def download_video(link, folder):
    try:
        ydl_opts = {'outtmpl': os.path.join(folder, '%(title)s.%(ext)s')}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])
    except:
        pass

@app.route("/download", methods=["POST"])
def download_api():
    data = request.json
    search_word = data.get("search_word")
    mode = data.get("mode", "both").lower()
    if not search_word:
        return {"error": "search_word is required"}, 400
    temp_folder = os.path.join(os.getcwd(), "downloads", f"{search_word}")
    os.makedirs(temp_folder, exist_ok=True)
    downloaded_image_urls = set()
    downloaded_video_urls = set()
    threads = []
    if mode in ["images", "both"]:
        t = threading.Thread(target=google_image_worker, args=(search_word, temp_folder, downloaded_image_urls))
        t.start()
        threads.append(t)
    if mode in ["videos", "both"]:
        t = threading.Thread(target=google_video_worker, args=(search_word, temp_folder, downloaded_video_urls))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for root, _, files in os.walk(temp_folder):
            for file in files:
                zipf.write(os.path.join(root, file), arcname=file)
    zip_buffer.seek(0)
    for root, _, files in os.walk(temp_folder):
        for file in files:
            os.remove(os.path.join(root, file))
    return send_file(zip_buffer, mimetype="application/zip", as_attachment=True, download_name=f"{search_word}_{mode}.zip")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
