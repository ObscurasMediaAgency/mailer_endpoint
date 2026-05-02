# Mailer Endpoint

Interner HTTP-Mail-Relay-Dienst. Server B sendet Mailanfragen an diesen Endpoint auf Server A (Plesk), der sie über ein konfiguriertes Plesk-Mailkonto zustellt.

---

## Projektstruktur

```
mailer_enpoint/
├── main.py           # FastAPI-App, Routing, Authentifizierung
├── mailer.py         # SMTP-Logik & MIME-Aufbau
├── models.py         # Pydantic-Schemas (Request / Response)
├── config.py         # Einstellungen aus .env
├── .env.example      # Konfigurationsvorlage
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Voraussetzungen

- Python 3.11+
- Ein Plesk-Mailkonto mit SMTP-Zugang (STARTTLS, Port 587)
- Auf Server A: Zugriff per SSH mit Superuser-Rechten

---

## Deployment auf Server A (Plesk)

### 1. Code übertragen

```bash
scp -r ./mailer_enpoint user@serverA:/opt/mailer_endpoint
# oder per git clone, wenn ein Repository vorhanden ist
```

### 2. Virtuelle Umgebung einrichten

```bash
cd /opt/mailer_endpoint
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Konfiguration anlegen

```bash
cp .env.example .env
nano .env
```

Felder in `.env` befüllen:

| Variable | Beschreibung |
|---|---|
| `SMTP_HOST` | Plesk-Mailserver, z. B. `mail.ihre-domain.de` |
| `SMTP_PORT` | `587` (STARTTLS) |
| `SMTP_USER` | Vollständige Mailadresse des Plesk-Kontos |
| `SMTP_PASSWORD` | Passwort des Plesk-Kontos |
| `SMTP_USE_TLS` | `true` |
| `SMTP_FROM_EMAIL` | Absenderadresse (identisch mit `SMTP_USER`) |
| `API_KEY` | Langen zufälligen Schlüssel eintragen (s. u.) |
| `RATE_LIMIT` | z. B. `20/minute` |

API-Key generieren:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Systemd-Service einrichten (Autostart)

Datei `/etc/systemd/system/mailer-endpoint.service` anlegen:

```ini
[Unit]
Description=Mailer Endpoint
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/mailer_endpoint
EnvironmentFile=/opt/mailer_endpoint/.env
ExecStart=/opt/mailer_endpoint/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8025
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable mailer-endpoint
systemctl start mailer-endpoint
systemctl status mailer-endpoint
```

### 5. Reverse Proxy in Plesk (Nginx)

In der Plesk-Oberfläche unter **Domains → ihre-domain.de → Apache & Nginx → Zusätzliche Nginx-Direktiven** eintragen:

```nginx
location /mailer/ {
    proxy_pass         http://127.0.0.1:8025/;
    proxy_set_header   Host              $host;
    proxy_set_header   X-Real-IP         $remote_addr;
    proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;
}
```

Der Endpoint ist danach erreichbar unter:
`https://ihre-domain.de/mailer/send`

### 6. Firewall absichern

Port 8025 darf **nicht** direkt nach außen erreichbar sein — nur über den Reverse Proxy:

```bash
# Direkten Zugriff auf Port 8025 von außen blockieren
ufw deny 8025
# oder mit iptables:
iptables -A INPUT -p tcp --dport 8025 ! -s 127.0.0.1 -j DROP
```

---

## Nutzung (Server B)

### Einfache Text-Mail

```bash
curl -X POST https://ihre-domain.de/mailer/send \
  -H "X-API-Key: DEIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "to": ["empfaenger@example.com"],
    "subject": "Hallo von Server B",
    "body_text": "Diese Mail wurde über den Relay-Endpoint gesendet."
  }'
```

### HTML-Mail mit CC

```json
{
  "to": ["empfaenger@example.com"],
  "cc": ["kopie@example.com"],
  "subject": "HTML-Mail",
  "body_html": "<h1>Hallo!</h1><p>Das ist eine <b>HTML</b>-Mail.</p>"
}
```

### Mail mit Anhang

```json
{
  "to": ["empfaenger@example.com"],
  "subject": "Rechnung",
  "body_text": "Anbei die Rechnung.",
  "attachments": [
    {
      "filename": "rechnung.pdf",
      "content_type": "application/pdf",
      "data": "BASE64_KODIERTER_DATEIINHALT"
    }
  ]
}
```

Base64 erzeugen (Linux):
```bash
base64 -w 0 rechnung.pdf
```

---

## API-Referenz

Nach dem Start ist die interaktive Dokumentation verfügbar unter:
`https://ihre-domain.de/mailer/docs`

> **Hinweis:** In der Produktion empfiehlt es sich, die Swagger-UI zu deaktivieren.
> Dazu in [main.py](main.py) die Parameter `docs_url=None, redoc_url=None` in der `FastAPI(...)`-Initialisierung einkommentieren.

---

## Liveness-Check

```bash
curl https://ihre-domain.de/mailer/health
# {"status":"ok"}
```
