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
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)
lock = threading.Lock()

# ---------------- IMAGE ----------------
def google_image_worker(search_word, folder, downloaded_image_urls, count):
    BASE_URL = "https://www.google.com/search?q={word}&tbm=isch&safe=off&start={start}"
    start = 0
    headers = {"User-Agent": "Mozilla/5.0"}
    counter_images = itertools.count(1)

    while len(downloaded_image_urls) < count and start < 200:
        try:
            url = BASE_URL.format(word=search_word, start=start)
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")
            images = soup.find_all("img")
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
                    if len(downloaded_image_urls) >= count:
                        break
                except:
                    continue
            start += 20
        except:
            time.sleep(2)

# ---------------- VIDEO ----------------
def google_video_worker(search_word, folder, downloaded_video_urls, count):
    BASE_URL = "https://www.google.com/search?q={word}&tbm=vid&safe=off&start={start}"
    start = 0
    headers = {"User-Agent": "Mozilla/5.0"}

    while len(downloaded_video_urls) < count and start < 100:
        try:
            url = BASE_URL.format(word=search_word, start=start)
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")
            video_links = []
            for a in soup.find_all("a"):
                href = a.get("href")
                if href and href.startswith("/url?q="):
                    parsed = parse_qs(urlparse(href).query)
                    if "q" in parsed:
                        real_url = unquote(parsed["q"][0])
                        video_links.append(real_url)
            for link in video_links:
                with lock:
                    if link in downloaded_video_urls:
                        continue
                    downloaded_video_urls.add(link)
                download_video(link, folder)
                if len(downloaded_video_urls) >= count:
                    break
            start += 10
        except:
            time.sleep(2)

def download_video(link, folder):
    try:
        ydl_opts = {'outtmpl': os.path.join(folder, '%(title)s.%(ext)s')}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])
    except:
        pass

# ---------------- API ----------------
@app.route("/download", methods=["POST"])
def download_api():
    data = request.json
    search_word = data.get("search_word")
    mode = data.get("mode", "both").lower()
    image_count = int(data.get("image_count", 5))
    video_count = int(data.get("video_count", 2))

    if not search_word:
        return {"error": "search_word is required"}, 400

    temp_folder = os.path.join(os.getcwd(), "downloads", search_word)
    os.makedirs(temp_folder, exist_ok=True)

    downloaded_image_urls = set()
    downloaded_video_urls = set()
    threads = []

    if mode in ["images", "both"]:
        t = threading.Thread(target=google_image_worker, args=(search_word, temp_folder, downloaded_image_urls, image_count))
        t.start()
        threads.append(t)
    if mode in ["videos", "both"]:
        t = threading.Thread(target=google_video_worker, args=(search_word, temp_folder, downloaded_video_urls, video_count))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    # Return list of file URLs for preview
    files = []
    for root, _, filenames in os.walk(temp_folder):
        for f in filenames:
            files.append(f"/media/{search_word}/{f}")

    return jsonify({"files": files})

# ---------------- Serve media files ----------------
@app.route("/media/<search>/<filename>")
def serve_media(search, filename):
    folder = os.path.join(os.getcwd(), "downloads", search)
    return send_file(os.path.join(folder, filename))

# ---------------- Run Flask ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
