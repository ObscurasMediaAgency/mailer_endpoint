"""
Zentrales Logging-Setup für den Mailer Endpoint.

Features:
- Rotating File Handler  → logs/mailer.log  (max. 5 MB, 5 Backups)
- Console Handler        → stdout (gleiche Formatierung)
- Separater Error-Handler→ logs/error.log   (nur WARNING+)
- Request-Middleware     → jede HTTP-Anfrage wird protokolliert
"""

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------
LOG_DIR = Path("logs")
LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)-30s  %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_BYTES = 5 * 1024 * 1024   # 5 MB pro Datei
BACKUP_COUNT = 5               # 5 rotierte Backups → max. 30 MB


def setup_logging(level: int = logging.INFO) -> None:
    """
    Richtet Root-Logger mit Console- und File-Handlern ein.
    Muss einmal beim App-Start aufgerufen werden.
    """
    LOG_DIR.mkdir(exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # --- Console ---
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    # --- Haupt-Logfile (rotierend) ---
    file_handler = RotatingFileHandler(
        LOG_DIR / "mailer.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # --- Error-Logfile (nur WARNING+) ---
    error_handler = RotatingFileHandler(
        LOG_DIR / "error.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.WARNING)

    root = logging.getLogger()
    root.setLevel(level)

    # Doppelte Handler vermeiden (z. B. bei Uvicorn-Reload)
    if not root.handlers:
        root.addHandler(console_handler)
        root.addHandler(file_handler)
        root.addHandler(error_handler)

    # Uvicorn-eigene Logger auf dieselben Handler umleiten
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = True


# ---------------------------------------------------------------------------
# Request-Logging-Middleware
# ---------------------------------------------------------------------------
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Protokolliert jede eingehende Anfrage mit Methode, Pfad,
    Client-IP, Status-Code und Verarbeitungsdauer."""

    _logger = logging.getLogger("mailer.access")

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        client_ip = request.headers.get("X-Forwarded-For", "")
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"

        self._logger.info(
            "%s %s %s | Status: %d | %.1f ms",
            client_ip,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
