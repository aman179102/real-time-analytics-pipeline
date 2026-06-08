from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

from src.config import config


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "service": config.service_name,
            "environment": config.environment.value,
        }

        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": "".join(
                    traceback.format_exception(*record.exc_info)
                ),
            }

        if hasattr(record, "extra"):
            log_entry["extra"] = record.extra

        return json.dumps(log_entry, default=str)


class StructuredLogger:
    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(config.log_level.value)

        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(StructuredFormatter())
            self._logger.addHandler(handler)

    def debug(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self._log(logging.DEBUG, message, correlation_id, extra, **kwargs)

    def info(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self._log(logging.INFO, message, correlation_id, extra, **kwargs)

    def warning(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self._log(logging.WARNING, message, correlation_id, extra, **kwargs)

    def error(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
        exc_info: bool = True,
        **kwargs: Any,
    ) -> None:
        self._log(
            logging.ERROR,
            message,
            correlation_id,
            extra,
            exc_info=exc_info,
            **kwargs,
        )

    def fatal(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self._log(logging.FATAL, message, correlation_id, extra, **kwargs)

    def _log(
        self,
        level: int,
        message: str,
        correlation_id: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "",
            0,
            message,
            (),
            None,
        )
        if correlation_id:
            record.correlation_id = correlation_id
        if extra:
            record.extra = extra
        for key, value in kwargs.items():
            setattr(record, key, value)
        self._logger.handle(record)


_loggers: dict[str, StructuredLogger] = {}


def get_logger(name: str) -> StructuredLogger:
    if name not in _loggers:
        _loggers[name] = StructuredLogger(name)
    return _loggers[name]
