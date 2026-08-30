"""Запись видео в сегменты с контролем хранилища."""

import glob
import threading
import os
import time
from datetime import datetime

import cv2
from utils.logger import Logger


class Recorder:
    """Записывает кадры в сегменты MP4, контролирует объём хранилища."""

    def __init__(self, camera_manager, segment_duration_minutes: int, recordings_dir: str):
        self.camera_manager = camera_manager
        self.segment_duration = segment_duration_minutes * 60  # секунды
        self.recording_enabled = True
        self.storage_limit_mb = 100 * 1024  # 100 ГБ в МБ
        self.video_writer = None
        self.current_segment_start = None
        self.current_segment_path = None
        self.running = True
        self._writer_lock = threading.Lock()
        self._recordings_dir = recordings_dir

        os.makedirs(self._recordings_dir, exist_ok=True)

    def run(self):
        Logger.log("Recorder: поток запущен")
        while not self.shutdown_event.is_set() and self.running:
            frame = self.camera_manager.get_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            if not self.recording_enabled or self.camera_manager.status != "connected":
                time.sleep(0.05)
                continue

            now = time.time()
            with self._writer_lock:
                if self.video_writer is None:
                    self._start_new_segment(now)
                elif now - self.current_segment_start >= self.segment_duration:
                    self.video_writer.release()
                    self.video_writer = None
                    self._start_new_segment(now)

            with self._writer_lock:
                if self.video_writer is not None:
                    self.video_writer.write(frame)

            if int(now) % 30 == 0:
                self._check_storage_limit()

            time.sleep(0.03)

        self.stop_recording()
        Logger.log("Recorder: поток остановлен")

    def _start_new_segment(self, now: float):
        filename = f"recording_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.mp4"
        filepath = os.path.join(self._recordings_dir, filename)

        frame = self.camera_manager.get_frame()
        if frame is None:
            return
        h, w = frame.shape[:2]
        fps = 30.0

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(filepath, fourcc, fps, (w, h))
        if not writer.isOpened():
            Logger.log(f"Recorder: не удалось открыть VideoWriter для {filepath}")
            return

        self.current_segment_path = filepath
        self.current_segment_start = now
        self.video_writer = writer
        Logger.log(f"Recorder: создан сегмент {filename}")

    def _check_storage_limit(self):
        total_bytes = 0
        files = self._list_mp4_files()
        for f in files:
            try:
                total_bytes += os.path.getsize(f)
            except OSError:
                pass

        total_mb = total_bytes / (1024 * 1024)
        if total_mb > self.storage_limit_mb:
            Logger.log(f"Recorder: превышен лимит хранилища ({total_mb:.1f} МБ > {self.storage_limit_mb} МБ)")
            self._delete_oldest_files()

    def _list_mp4_files(self) -> list:
        pattern = os.path.join(self._recordings_dir, "*.mp4")
        files = glob.glob(pattern)
        files.sort(key=os.path.getmtime, reverse=True)
        return files

    def _delete_oldest_files(self):
        files = self._list_mp4_files()
        total_bytes = sum(os.path.getsize(f) for f in files if os.path.exists(f))
        for f in files:
            if total_bytes <= self.storage_limit_mb * 1024 * 1024:
                break
            try:
                size = os.path.getsize(f)
                os.remove(f)
                total_bytes -= size
                Logger.log(f"Recorder: удалён старый файл {os.path.basename(f)}")
            except OSError as e:
                Logger.log(f"Recorder: ошибка удаления {f}: {e}")

    def start_recording(self):
        self.recording_enabled = True
        Logger.log("Recorder: запись включена")

    def stop_recording(self):
        self.recording_enabled = False
        with self._writer_lock:
            if self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None
                Logger.log("Recorder: текущий сегмент закрыт")

    def get_storage_used_mb(self) -> float:
        total = 0
        for f in self._list_mp4_files():
            try:
                total += os.path.getsize(f)
            except OSError:
                pass
        return total / (1024 * 1024)

    def set_storage_limit_mb(self, limit_mb: float):
        self.storage_limit_mb = limit_mb
        Logger.log(f"Recorder: лимит хранилища изменён на {limit_mb} МБ")
        self._check_storage_limit()

    def get_recordings(self) -> list:
        files = self._list_mp4_files()
        result = []
        for f in files:
            if os.path.exists(f):
                name = os.path.basename(f)
                # Не показываем текущий записываемый файл
                if self.current_segment_path and os.path.basename(self.current_segment_path) == name:
                    continue
                mtime = os.path.getmtime(f)
                dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                duration = self._get_duration(f)
                size = self._get_size(f)
                result.append({"name": name, "date": dt, "duration": duration, "size": size})
        return result

    @staticmethod
    def _get_duration(filepath: str) -> str:
        """Возвращает длительность видео в формате М:СС."""
        try:
            cap = cv2.VideoCapture(filepath)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                cap.release()
                if fps > 0 and frames > 0:
                    total_seconds = int(frames / fps)
                    m = total_seconds // 60
                    s = total_seconds % 60
                    return f"{m}:{s:02d}"
            else:
                cap.release()
        except Exception:
            pass
        return "—"

    @staticmethod
    def _get_size(filepath: str) -> str:
        """Возвращает размер файла в читаемом виде."""
        try:
            size_bytes = os.path.getsize(filepath)
            if size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} КБ"
            else:
                return f"{size_bytes / (1024 * 1024):.1f} МБ"
        except OSError:
            return "—"

    def stop(self):
        self.running = False

    @property
    def shutdown_event(self):
        import __main__
        return __main__.shutdown_event
