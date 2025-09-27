import os
import requests
from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PEXELS_API_KEY = "YOUR_PEXELS_API_KEY"  # get from https://www.pexels.com/api/

def download_media_from_pexels(query, image_count=5, video_count=2):
    folder = os.path.join("downloads", query)
    os.makedirs(folder, exist_ok=True)
    files = []

    headers = {"Authorization": PEXELS_API_KEY}

    # ---- Images ----
    if image_count > 0:
        img_resp = requests.get(f"https://api.pexels.com/v1/search?query={query}&per_page={image_count}", headers=headers).json()
        for i, photo in enumerate(img_resp.get("photos", []), 1):
            url = photo["src"]["original"]
            file_path = os.path.join(folder, f"{query}_img_{i}.jpg")
            r = requests.get(url)
            with open(file_path, "wb") as f:
                f.write(r.content)
            files.append(f"/media/{query}/{query}_img_{i}.jpg")

    # ---- Videos ----
    if video_count > 0:
        vid_resp = requests.get(f"https://api.pexels.com/videos/search?query={query}&per_page={video_count}", headers=headers).json()
        for i, vid in enumerate(vid_resp.get("videos", []), 1):
            url = vid["video_files"][0]["link"]
            file_path = os.path.join(folder, f"{query}_vid_{i}.mp4")
            r = requests.get(url)
            with open(file_path, "wb") as f:
                f.write(r.content)
            files.append(f"/media/{query}/{query}_vid_{i}.mp4")

    return files

# ---- API ----
@app.route("/download", methods=["POST"])
def download_api():
    data = request.json
    query = data.get("search_word")
    images = int(data.get("image_count", 5))
    videos = int(data.get("video_count", 2))

    if not query:
        return {"error": "search_word required"}, 400

    files = download_media_from_pexels(query, images, videos)
    return jsonify({"files": files})

# ---- Serve media ----
@app.route("/media/<search>/<filename>")
def serve_media(search, filename):
    folder = os.path.join("downloads", search)
    file_path = os.path.join(folder, filename)
    if not os.path.exists(file_path):
        abort(404)
    return send_file(file_path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
