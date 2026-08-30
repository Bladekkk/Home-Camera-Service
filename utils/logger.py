"""Потокобезопасный логгер в файл."""

import threading
from datetime import datetime


class Logger:
    _lock = threading.Lock()

    @staticmethod
    def log(message: str, log_file: str = "logs.txt"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {message}\n"
        with Logger._lock:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line)
            print(line.rstrip())
