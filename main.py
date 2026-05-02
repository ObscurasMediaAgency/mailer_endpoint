import logging
import secrets

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import APIKeyHeader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from config import settings
from log_config import RequestLoggingMiddleware, setup_logging
from mailer import send_email
from models import EmailRequest, EmailResponse

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
setup_logging()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Mailer Endpoint",
    description="Interner Mail-Relay-Dienst für Server B → Server A (Plesk).",
    version="1.0.0",
    # Swagger-UI und ReDoc in Produktion ggf. deaktivieren:
    # docs_url=None, redoc_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(RequestLoggingMiddleware)

# ---------------------------------------------------------------------------
# Authentifizierung
# ---------------------------------------------------------------------------
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Depends(api_key_header)) -> str:
    """Prüft den API-Key mittels zeitkonstantem Vergleich (Timing-Attack-safe)."""
    if not api_key or not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Ungültiger oder fehlender API-Key")
    return api_key


# ---------------------------------------------------------------------------
# Endpunkte
# ---------------------------------------------------------------------------
@app.get("/health", tags=["System"])
async def health() -> dict[str, str]:
    """Einfacher Liveness-Check – keine Authentifizierung erforderlich."""
    return {"status": "ok"}


@app.post(
    "/send",
    response_model=EmailResponse,
    dependencies=[Depends(verify_api_key)],
    tags=["Mail"],
    summary="E-Mail versenden",
)
@limiter.limit(settings.rate_limit)  # type: ignore[misc]
async def send_mail_endpoint(request: Request, email: EmailRequest) -> EmailResponse:
    """
    Sendet eine E-Mail über das konfigurierte Plesk-Mailkonto.

    - **to**: Pflichtfeld, mindestens eine Adresse
    - **subject**: Betreff
    - **body_text** / **body_html**: mindestens eines muss gesetzt sein
    - **attachments**: optionale Liste mit Base64-kodierten Anhängen
    """
    if not email.has_body():
        raise HTTPException(
            status_code=422,
            detail="Mindestens 'body_text' oder 'body_html' muss angegeben werden.",
        )

    try:
        send_email(email)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("Fehler beim E-Mail-Versand")
        raise HTTPException(
            status_code=500,
            detail="Interner Fehler beim Versand. Details wurden serverseitig protokolliert.",
        )

    return EmailResponse(success=True, detail="E-Mail erfolgreich versendet.")
