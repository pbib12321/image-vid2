import time
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote
from flask import Flask, request, send_file, jsonify
from flask import Flask, request, send_file, jsonify, Response, abort
from flask_cors import CORS
import yt_dlp

@@ -83,7 +83,10 @@ def google_video_worker(search_word, folder, downloaded_video_urls, count):

def download_video(link, folder):
    try:
        ydl_opts = {'outtmpl': os.path.join(folder, '%(title)s.%(ext)s')}
        ydl_opts = {
            'outtmpl': os.path.join(folder, '%(title)s.%(ext)s'),
            'format': 'mp4/best'
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])
    except:
@@ -132,8 +135,35 @@ def download_api():
@app.route("/media/<search>/<filename>")
def serve_media(search, filename):
    folder = os.path.join(os.getcwd(), "downloads", search)
    return send_file(os.path.join(folder, filename))
    file_path = os.path.join(folder, filename)
    if not os.path.exists(file_path):
        abort(404)

    # Handle range requests for video streaming
    range_header = request.headers.get("Range", None)
    if not range_header:
        return send_file(file_path)

    size = os.path.getsize(file_path)
    byte1, byte2 = 0, None

    match = range_header.replace("bytes=", "").split("-")
    if match[0]:
        byte1 = int(match[0])
    if len(match) > 1 and match[1]:
        byte2 = int(match[1])

    length = size - byte1 if byte2 is None else byte2 - byte1 + 1
    with open(file_path, "rb") as f:
        f.seek(byte1)
        data = f.read(length)

    resp = Response(data, 206, mimetype="video/mp4",
                    content_type="video/mp4",
                    direct_passthrough=True)
    resp.headers.add("Content-Range", f"bytes {byte1}-{byte1 + length - 1}/{size}")
    return resp

# ---------------- Run Flask ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
