"""Flask-сервер с MJPEG-потоком и управлением записью."""

import os
import sys
import time
import logging

import cv2
import numpy as np
from flask import Flask, Response, request, jsonify, send_from_directory, render_template

from utils.logger import Logger

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


class WebServer:
    """Flask-сервер с MJPEG-потоком и управлением записью."""

    def __init__(self, camera_manager, recorder, port: int):
        self.camera_manager = camera_manager
        self.recorder = recorder
        self.port = port
        self.app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "server", "templates"))
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route("/")
        def index():
            recordings = self.recorder.get_recordings()
            return render_template("index.html", recordings=recordings)

        @self.app.route("/video_feed")
        def video_feed():
            return Response(
                self._mjpeg_generator(),
                mimetype="multipart/x-mixed-replace; boundary=frame"
            )

        @self.app.route("/status")
        def status():
            return jsonify({
                "camera": self.camera_manager.status,
                "recording": self.recorder.recording_enabled,
                "storage_used_mb": round(self.recorder.get_storage_used_mb(), 2),
                "storage_limit_mb": self.recorder.storage_limit_mb,
            })

        @self.app.route("/toggle_record", methods=["POST"])
        def toggle_record():
            if self.recorder.recording_enabled:
                self.recorder.stop_recording()
            else:
                self.recorder.start_recording()
            return jsonify({"recording": self.recorder.recording_enabled})

        @self.app.route("/set_limit", methods=["POST"])
        def set_limit():
            data = request.get_json(force=True)
            limit_mb = data.get("limit_mb", self.recorder.storage_limit_mb)
            if limit_mb > 0:
                self.recorder.set_storage_limit_mb(limit_mb)
            return jsonify({"storage_limit_mb": self.recorder.storage_limit_mb})

        @self.app.route("/download/<filename>")
        def download(filename):
            return send_from_directory(self.recorder._recordings_dir, filename, as_attachment=True)

        @self.app.route("/delete/<filename>", methods=["POST"])
        def delete(filename):
            filepath = os.path.join(self.recorder._recordings_dir, filename)
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    Logger.log(f"WebServer: файл удалён {filename}")
            except OSError as e:
                Logger.log(f"WebServer: ошибка удаления {filename}: {e}")
            return jsonify({"status": "ok"})

        @self.app.route("/shutdown", methods=["POST"])
        def shutdown():
            Logger.log("WebServer: запрос на остановку сервера")
            from utils.config import save_config
            save_config(
                self.camera_manager.camera_index,
                self.port,
                self.recorder.segment_duration // 60
            )
            self._shutdown_event.set()
            self.recorder.stop_recording()
            self.camera_manager.stop()
            time.sleep(0.5)
            sys.exit(0)

    def _mjpeg_generator(self):
        no_signal = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(no_signal, "NO SIGNAL", (180, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        _, buf = cv2.imencode(".jpg", no_signal)

        frame_count = 0

        while not self._shutdown_event.is_set():
            frame = self.camera_manager.get_frame()
            if frame is not None:
                frame_count += 1
                if frame_count % 3 != 0:
                    time.sleep(0.03)
                    continue
                ret, enc = cv2.imencode(".jpg", frame)
            else:
                enc = buf
                frame_count = 0

            if ret:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + enc.tobytes() + b"\r\n")
            time.sleep(0.03)

    def run(self):
        Logger.log(f"WebServer: запуск на порту {self.port}")
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.CRITICAL)
        self.app.run(host="0.0.0.0", port=self.port, threaded=True, use_reloader=False)

    @property
    def _shutdown_event(self):
        import __main__
        return __main__.shutdown_event
