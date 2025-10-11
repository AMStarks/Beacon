#!/usr/bin/env python3
"""
Beacon 3 Logging Configuration
"""

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
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
    """Setup logging configuration for Beacon 3"""
    global _logging_configured
    if _logging_configured:
        return

    # Resolve logs directory
    try:
        env_dir = os.environ.get("BEACON_LOG_DIR")
    except Exception:
        env_dir = None
    base_dir = Path(__file__).resolve().parent
    logs_path = Path(log_dir or env_dir or (base_dir / "logs"))
    logs_path.mkdir(parents=True, exist_ok=True)

    log_file_path = logs_path / "beacon3.log"

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

    # Clear existing handlers and add our handlers
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Silence overly chatty third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

    _logging_configured = True

    # Install global exception hooks
    try:
        import sys, asyncio

        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                return
            root_logger.error("UNCAUGHT: %s", str(exc_value), exc_info=(exc_type, exc_value, exc_traceback))

        sys.excepthook = handle_exception

        try:
            loop = asyncio.get_event_loop()

            def handle_async_exception(loop, context):
                msg = context.get("message") or str(context.get("exception"))
                root_logger.error("ASYNC-UNCAUGHT: %s", msg, extra={"context": context})

            loop.set_exception_handler(handle_async_exception)
        except Exception:
            pass
    except Exception:
        pass

    logger.info("✅ Beacon 3 logging configured")
