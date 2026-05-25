# Connecting a real live camera

The dashboard tiles, the inference pipeline, and the CEP rules all
consume the **`raw-frames` Kafka topic**. Anything you can persuade
OpenCV to open can feed that topic via `services/frame_grabber/grabber.py`.
Three concrete paths below — pick the one matching your hardware.

---

## Path 1 — Mac/PC built-in webcam (zero hardware cost)

The grabber now accepts a numeric device index. Index 0 = the default
camera (FaceTime on Mac, "Integrated Camera" on Windows).

```bash
# Grant the terminal Camera permission ONCE
# macOS: System Settings → Privacy & Security → Camera → enable Terminal/iTerm/VSCode
# Windows: Settings → Privacy → Camera → "Allow apps to access your camera"

make frame-grabber SOURCE=0 CAMERA=CAM01 FPS=5
# or directly:
uv run python -m services.frame_grabber.grabber --source 0 --camera-id CAM01 --fps 5
```

The grabber automatically detects a live source (numeric index OR
`rtsp://…` URL) and switches to a **rate-limited read loop** so the
buffer never grows — old frames are dropped, only the most recent one
is published at `target_fps`.

---

## Path 2 — Smartphone as an IP-camera (recommended for soutenance)

No new hardware. Install one of these apps on your phone — both expose
an RTSP or MJPEG-over-HTTP stream over Wi-Fi:

| App | Platform | URL pattern |
|---|---|---|
| **IP Webcam** | Android (free) | `http://<phone-ip>:8080/video` (MJPEG) |
| **DroidCam OBS** | iOS/Android (free) | `http://<phone-ip>:4747/video` (MJPEG) |
| **iVCam / EpocCam** | iOS (free tier) | RTSP via desktop client |
| **RTSP Server** | Android (paid) | `rtsp://<phone-ip>:8554/stream` |

```bash
# Find the phone's LAN IP (Settings → Wi-Fi → tap network → IP address)
# Then point the grabber at it:
make frame-grabber SOURCE=http://192.168.1.42:8080/video CAMERA=CAM01 FPS=5
# Or RTSP:
make frame-grabber SOURCE=rtsp://192.168.1.42:8554/stream CAMERA=CAM02 FPS=5
```

Run **one grabber per camera** in its own terminal — each maps to a
distinct `--camera-id` and shows as a separate tile in the dashboard.

---

## Path 3 — True IP / PoE cameras (production)

Any RTSP-capable IP camera (Hikvision, Reolink, generic ONVIF) works.
The pipeline is identical to Path 2 — just swap the URL:

```bash
# Substitute your camera's user / password / IP / channel
make frame-grabber SOURCE='rtsp://<USER>:<PASS>@10.0.0.42:554/Streaming/Channels/101' \
                   CAMERA=CAM01 FPS=5
```

For 3+ cameras we recommend deploying **MediaMTX** as a relay (already
in `infra/mediamtx/` of the original design): one RTSP pull from
MediaMTX per grabber, MediaMTX handles reconnection + transcoding.

```yaml
# infra/mediamtx/mediamtx.yml — add an entry per real camera
# Replace <USER>/<PASS>/<IP> with your camera's actual credentials.
paths:
  cam01:
    source: rtsp://<USER>:<PASS>@<IP_CAM01>:554/Streaming/Channels/101
    sourceProtocol: tcp
  cam02:
    source: rtsp://<USER>:<PASS>@<IP_CAM02>:554/Streaming/Channels/101
    sourceProtocol: tcp
```

Then the grabbers pull from `rtsp://localhost:8554/cam01`, `…/cam02`, …
which is way more robust than each grabber holding a direct camera
connection.

---

## Wiring it back into the dashboard

The dashboard's MJPEG streaming endpoint (`/api/cameras/{id}/stream.mjpg`)
currently serves files from `data/raw/videos/`. To make it serve **live
camera feeds** instead, set per-camera source URLs in
`infra/cameras.example.yaml`:

```yaml
cameras:
  - id: CAM01
    name: Entrée Principale
    source: 0                              # USB webcam
  - id: CAM02
    name: Quai d'Expédition
    source: http://192.168.1.42:8080/video # phone MJPEG
  - id: CAM03
    name: Allée Stockage A1-A2
    source: rtsp://10.0.0.42:554/stream    # IP camera
```

`services/api/routers/stream.py::_video_for_camera` already prefers
explicit per-camera mapping over the filename heuristic — drop a
`source:` field into the YAML and the tile will stream it live.

---

## Failure modes & fallbacks

| Symptom | Cause | Fix |
|---|---|---|
| `Could not open video source` on macOS | Terminal lacks Camera permission | System Settings → Privacy & Security → Camera → enable your terminal |
| Tile is black / status pill = `live · feed only` | Kafka `raw-frames` has no recent message for that camera | Grabber not running; `make frame-grabber SOURCE=... CAMERA=...` |
| Stream stutters or drops frames | Grabber is buffering — wrong source detected as file | The grabber auto-detects via `isdigit()` / `rtsp://` / `http://`. Ensure URL is full (scheme included). |
| Dashboard shows ⚪ "feed only" badge but inference is running | Worker is processing, but raw-frame timestamps are older than 30 s | Increase the grabber FPS or check that frames aren't being throttled too aggressively |
| Inference produces 0 boxes on the live feed | YOLO trained on classes that aren't in your camera's field of view | Use COCO weights (`MODEL_FALLBACK=$(pwd)/yolov8n.pt DETECTION_CONF=0.20`) or fine-tune on samples from your actual camera |
