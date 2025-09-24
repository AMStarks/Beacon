from __future__ import annotations

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class JsonFormatter(logging.Formatter):
    default_time_format = "%Y-%m-%dT%H:%M:%S"

    def format(self, record: logging.LogRecord) -> str:
        log_payload = {
            "timestamp": self.formatTime(record, self.default_time_format),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            log_payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(log_payload, ensure_ascii=False)


_logging_configured = False


def setup_logging(log_dir: Optional[str] = None, level: int = logging.INFO) -> None:
    global _logging_configured
    if _logging_configured:
        return

    logs_path = Path(log_dir or "logs")
    logs_path.mkdir(parents=True, exist_ok=True)

    log_file_path = logs_path / "beacon.log"

    formatter = JsonFormatter()

    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [file_handler, console_handler]

    # Silence overly chatty third-party loggers unless escalated
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

    _logging_configured = True

