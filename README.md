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
- Plesk-Server mit lokalem MTA (Postfix), der auf Port 25 lauscht
- Auf Server A: Zugriff per SSH mit Superuser-Rechten
- DNS-A-Record `mailer.ihre-domain.de` → IP-Adresse des Servers

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
| `SMTP_HOST` | `localhost` (lokaler Plesk-MTA) |
| `SMTP_PORT` | `25` (lokaler Postfix, kein TLS) |
| `SMTP_USER` | Vollständige Mailadresse des Plesk-Kontos |
| `SMTP_PASSWORD` | Passwort des Plesk-Kontos |
| `SMTP_USE_TLS` | `false` |
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
User=apache
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

### 5. Subdomain & Reverse Proxy in Plesk (Nginx)

**5a. DNS** – A-Record beim DNS-Anbieter anlegen:
```
mailer.ihre-domain.de.  IN  A  <IP-Adresse des Servers>
```

**5b. Subdomain in Plesk anlegen** – unter **Domains → ihre-domain.de → Subdomains → Subdomain hinzufügen**:
- Name: `mailer`
- Anschließend unter der neuen Subdomain ein Let's-Encrypt-Zertifikat ausstellen lassen

**5c. Nginx-Proxy** – in der Plesk-Oberfläche unter **Domains → mailer.ihre-domain.de → Apache & Nginx → Zusätzliche Nginx-Direktiven** die API-Pfade einzeln eintragen:

```nginx
location /send {
  proxy_pass         http://127.0.0.1:8025/send;
  proxy_set_header   Host              $host;
  proxy_set_header   X-Real-IP         $remote_addr;
  proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
  proxy_set_header   X-Forwarded-Proto $scheme;
}

location /health {
  proxy_pass         http://127.0.0.1:8025/health;
  proxy_set_header   Host              $host;
  proxy_set_header   X-Real-IP         $remote_addr;
  proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
  proxy_set_header   X-Forwarded-Proto $scheme;
}

location /docs {
  proxy_pass         http://127.0.0.1:8025/docs;
  proxy_set_header   Host              $host;
  proxy_set_header   X-Real-IP         $remote_addr;
  proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
  proxy_set_header   X-Forwarded-Proto $scheme;
}

location /openapi.json {
  proxy_pass         http://127.0.0.1:8025/openapi.json;
  proxy_set_header   Host              $host;
  proxy_set_header   X-Real-IP         $remote_addr;
  proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
  proxy_set_header   X-Forwarded-Proto $scheme;
}
```

Kein zusätzliches `location / { ... }` eintragen. Plesk erzeugt dafür bereits selbst einen Standard-Block; ein zweiter Block führt zu `duplicate location "/"` beim Nginx-Test.

Der Endpoint ist danach erreichbar unter:
`https://mailer.ihre-domain.de/send`

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
curl -X POST https://mailer.ihre-domain.de/send \
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
`https://mailer.ihre-domain.de/docs`

> **Hinweis:** In der Produktion empfiehlt es sich, die Swagger-UI zu deaktivieren.
> Dazu in [main.py](main.py) die Parameter `docs_url=None, redoc_url=None` in der `FastAPI(...)`-Initialisierung einkommentieren.

---

## Liveness-Check

```bash
curl https://mailer.ihre-domain.de/health
# {"status":"ok"}
```
