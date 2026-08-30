#!/usr/bin/env python3
"""
Система видеонаблюдения с веб-интерфейсом.
Запуск: python main.py
"""

import io
import os
import socket
import sys
import threading
import time

import cv2
from utils.logger import Logger
from utils.config import load_config, save_config, DEFAULT_CONFIG, CONFIG_FILE
from models.camera_manager import CameraManager
from models.recorder import Recorder
from server.web_server import WebServer

# ---------------------------------------------------------------------------
# Подавление OpenCV-предупреждений
# ---------------------------------------------------------------------------
import logging
logging.getLogger("cv2").setLevel(logging.ERROR)
logging.getLogger("obsensor").setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# Глобальный флаг остановки
# ---------------------------------------------------------------------------
shutdown_event = threading.Event()

# ---------------------------------------------------------------------------
# Пути
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")


# ---------------------------------------------------------------------------
# Вспомогательные функции ввода
# ---------------------------------------------------------------------------
def select_camera_index(default: int = 0) -> int:
    """Запрашивает у пользователя индекс камеры."""
    import io
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()

    available = []
    for i in range(6):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            cap.release()
            available.append(i)
        else:
            cap.release()

    sys.stderr = old_stderr

    if not available:
        print("Камеры не обнаружены. Введите индекс вручную (0, 1, 2…).")
    else:
        print(f"Доступные камеры: {available}")

    while True:
        try:
            val = input(f"Выберите номер камеры [{default}]: ").strip()
            idx = int(val) if val else default
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                cap.release()
                return idx
            else:
                cap.release()
                print("Невалидный индекс. Попробуйте снова.")
        except ValueError:
            print("Введите число.")


def select_port(default: int = 3222) -> int:
    """Запрашивает порт, проверяет что он свободен."""
    import socket
    while True:
        val = input(f"Порт для веб-сервера [{default}]: ").strip()
        port = int(val) if val else default
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("0.0.0.0", port))
            sock.close()
            return port
        except OSError:
            print(f"Порт {port} занят. Выберите другой.")


def select_segment_duration(default: int = 5) -> int:
    """Запрашивает длительность сегмента в минутах."""
    while True:
        val = input(f"Длительность сегмента (мин) [{default}]: ").strip()
        try:
            d = int(val) if val else default
            if d > 0:
                return d
            print("Должно быть больше 0.")
        except ValueError:
            print("Введите число.")


def _get_local_ip() -> str:
    """Получает локальный IP-адрес машины."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def confirm_use_config(cfg: dict) -> bool:
    """Спрашивает пользователя, использовать ли предыдущие настройки."""
    print("\nНайдены предыдущие настройки:")
    print(f"  Камера: {cfg['camera_index']}")
    print(f"  Порт: {cfg['port']}")
    print(f"  Длительность сегмента: {cfg['segment_duration_minutes']} мин")
    while True:
        val = input("Использовать? (y/n): [y]").strip().lower()
        if val in ("y", "yes", "да", "д") or val == '':
            return True
        if val in ("n", "no", "нет", "н"):
            return False
        print("Введите y или n.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    Logger.log("=" * 60)
    Logger.log("Home Camera Service: запуск")
    Logger.log("=" * 60)

    os.makedirs(RECORDINGS_DIR, exist_ok=True)

    # Загрузка настроек
    cfg = load_config()
    if cfg:
        if confirm_use_config(cfg):
            cam_idx = cfg["camera_index"]
            port = cfg["port"]
            segment_min = cfg["segment_duration_minutes"]
            Logger.log("Использованы предыдущие настройки")
        else:
            cam_idx = select_camera_index(cfg["camera_index"])
            port = select_port(cfg["port"])
            segment_min = select_segment_duration(cfg["segment_duration_minutes"])
    else:
        cam_idx = select_camera_index()
        port = select_port(3222)
        segment_min = select_segment_duration(5)

    # Получаем локальный IP
    local_ip = _get_local_ip()

    print(f"\nНастройки: камера={cam_idx}, порт={port}, сегмент={segment_min} мин")
    print("Запуск компонентов…\n")

    camera_manager = CameraManager(cam_idx)
    recorder = Recorder(camera_manager, segment_min, RECORDINGS_DIR)
    web_server = WebServer(camera_manager, recorder, port)

    cam_thread = threading.Thread(target=camera_manager.run, daemon=True, name="CameraManager")
    rec_thread = threading.Thread(target=recorder.run, daemon=True, name="Recorder")
    web_thread = threading.Thread(target=web_server.run, daemon=True, name="WebServer")

    cam_thread.start()
    rec_thread.start()
    web_thread.start()

    print(f"Веб-интерфейс доступен по адресу: http://{local_ip}:{port}")
    print("Нажмите Ctrl+C для остановки.\n")

    try:
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=1.0)
    except KeyboardInterrupt:
        print("\nОстановка…")
        shutdown_event.set()

    recorder.stop_recording()
    camera_manager.stop()
    cam_thread.join(timeout=3)
    rec_thread.join(timeout=3)
    Logger.log("Home Camera Service: остановлен")
    sys.exit(0)


if __name__ == "__main__":
    main()
