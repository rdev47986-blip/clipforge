from flask import Flask, request, jsonify, send_from_directory
from pathlib import Path
import subprocess, uuid, os

app = Flask(__name__)
ROOT = Path(__file__).resolve().parent
UPLOADS = ROOT / "uploads"
OUTPUTS = ROOT / "outputs"
UPLOADS.mkdir(exist_ok=True)
OUTPUTS.mkdir(exist_ok=True)

@app.get("/")
def home():
    return send_from_directory(ROOT, "index.html")

@app.post("/api/clips")
def clips():
    f = request.files.get("video")
    if not f or not f.filename:
        return jsonify(error="Please upload a video file."), 400
    try:
        clip_len = int(request.form.get("length", "30"))
        count = int(request.form.get("count", "3"))
    except ValueError:
        return jsonify(error="Invalid clip settings."), 400
    clip_len = max(10, min(clip_len, 120))
    count = max(1, min(count, 10))
    job = uuid.uuid4().hex
    source = UPLOADS / f"{job}_{Path(f.filename).name}"
    f.save(source)
    # Use ffprobe to read duration.
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(source)
    ], capture_output=True, text=True, check=True)
    duration = float(probe.stdout.strip())
    if duration <= 0:
        return jsonify(error="Could not read video duration."), 400
    # Pick evenly spaced start points, avoiding overlap where possible.
    max_start = max(0, duration - clip_len)
    starts = [max_start * i / max(1, count-1) for i in range(count)]
    results = []
    for i, start in enumerate(starts, 1):
        out = OUTPUTS / f"{job}_clip{i}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(start), "-i", str(source),
            "-t", str(min(clip_len, duration-start)),
            "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-movflags", "+faststart", str(out)
        ], check=True, capture_output=True)
        results.append({"name": f"Clip {i}", "url": f"/outputs/{out.name}"})
    return jsonify(clips=results)

@app.get("/outputs/<path:name>")
def output_file(name):
    return send_from_directory(OUTPUTS, name, as_attachment=True)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
