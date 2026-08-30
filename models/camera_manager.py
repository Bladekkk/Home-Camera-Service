"""Менеджер камеры: открывает и поддерживает подключение."""

import threading
import time

import cv2
from utils.logger import Logger


class CameraManager:
    """Открывает камеру в отдельном потоке, хранит последний кадр."""

    def __init__(self, camera_index: int):
        self.camera_index = camera_index
        self.cap = None
        self.last_frame = None
        self.status = "disconnected"
        self.lock = threading.Lock()
        self.running = True

    def run(self):
        Logger.log(f"CameraManager: поток запущен, индекс={self.camera_index}")
        while not self.shutdown_event.is_set() and self.running:
            if self.status != "connected":
                self._reconnect()
            if self.status != "connected":
                continue
            ret, frame = self.cap.read()
            if not ret or frame is None:
                Logger.log("CameraManager: кадр не получен, переподключение…")
                self.status = "disconnected"
                self.cap.release()
                self.cap = None
                continue
            with self.lock:
                self.last_frame = frame
        self._cleanup()
        Logger.log("CameraManager: поток остановлен")

    def _reconnect(self):
        Logger.log(f"CameraManager: попытка подключения к камере {self.camera_index}")
        self.cap = cv2.VideoCapture(self.camera_index)
        time.sleep(0.5)
        if self.cap.isOpened():
            self.status = "connected"
            Logger.log(f"CameraManager: камера {self.camera_index} подключена")
        else:
            self.cap.release()
            self.cap = None
            Logger.log(f"CameraManager: камера {self.camera_index} недоступна, жду 2 сек")
            time.sleep(2)

    def get_frame(self):
        with self.lock:
            if self.last_frame is not None:
                return self.last_frame.copy()
        return None

    def _cleanup(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def stop(self):
        self.running = False

    @property
    def shutdown_event(self):
        import __main__
        return __main__.shutdown_event
