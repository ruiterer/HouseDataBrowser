# HouseDataBrowser

> **Status:** persoonlijk hobbyproject — gebouwd voor mijn eigen situatie. Werkt voor mij; geen ondersteuning of onderhoud beloofd.

Een webapp om de data uit je InfluxDB van je huis te verkennen **in natuurlijke taal**
(Nederlands), zonder zelf InfluxQL te hoeven typen. Stel vragen als
*"Vergelijk de elektriciteitsproductie van zomer 2024 met zomer 2023"* en je krijgt
een grafiek, een tabel, een geschreven samenvatting en de gegenereerde query terug.
Grafieken die je vaak gebruikt kun je vastzetten op een Dashboard.

## Architectuur

- **Backend**: FastAPI (Python 3.12) — draait een LLM-agent-loop, beheert de
  InfluxDB-verbinding, dwingt een read-only query-filter af, indexeert het schema.
- **Frontend**: React + TypeScript (Vite) — chat-UX, Plotly-grafieken,
  schema-browser, draaibaar Dashboard van vastgezette grafieken.
- **State**: SQLite (chat-historie, vastgezette grafieken, schema-annotaties).
- **LLM**: pluggable. **Claude API** standaard; switch naar **Ollama** (bv. op een
  Raspberry Pi 5) door één env-variabele te wijzigen.
- **Deployment**: Docker-container op hetzelfde LAN als je bestaande InfluxDB.

## Status

- ✅ Fase 1 — backend + frontend skeleton, InfluxQL safety filter (28 tests groen)
- ✅ Fase 2 — schema-ontdekking + Schema-pagina met bewerkbare beschrijvingen
- ✅ Fase 3 — LLM-agent-loop met streaming SSE, Plotly-grafieken, debug-paneel,
  per-vraag "Diep nadenken"-knop, Nederlandse UI
- ✅ Fase 4 — vastgezette grafieken op een sleepbaar Dashboard (queries blijven
  vers omdat ze opnieuw gedraaid worden bij het laden)
- ✅ Fase 5 — Ollama-provider met tool-calling voor lokale modellen
- ✅ Fase 5b — UI om tijdens het chatten te wisselen tussen providers en
  modellen (Claude / Ollama, met live model-lijst van Ollama)

## Snel beginnen

### 1. Configureer

```bash
cp .env.example .env
```

Bewerk `.env`:

- `INFLUX_HOST/PORT/DATABASE` → wijzen naar je bestaande InfluxDB
- `ANTHROPIC_API_KEY` → vereist als `LLM_PROVIDER=claude`
- `LLM_PROVIDER=claude` (default) of `ollama`
- `LLM_MODEL=claude-opus-4-7` of `LLM_EFFORT=high` (low/medium/high/max)

### 2. Lokaal draaien (twee processen)

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxiet `/api/*` naar de backend op poort 8000.

### 3. Tests draaien

```bash
cd backend
pytest
```

### 4. Productie (Docker)

```bash
docker compose up --build -d
```

Open http://localhost:8000. De image bundelt de gebouwde React-app, geserveerd
door FastAPI.

## Tijdens chatten van provider en model wisselen

Onder de chat-invoer staan twee dropdowns:

- **Provider** — *Claude (cloud)* of *Ollama (lokaal)*. Een provider die niet
  bereikbaar is (geen API key, of Ollama draait niet) staat grijs en kan niet
  gekozen worden.
- **Model** — voor Claude een vaste lijst (Opus 4.7 / 4.6, Sonnet 4.6,
  Haiku 4.5). Voor Ollama de live lijst van modellen die je op de host hebt
  gepulled (live opgehaald via `/api/tags`).

Je keuze persisteert in `localStorage`, dus na een refresh begin je weer met
dezelfde combinatie. De **🧠 Diep nadenken**-knop wordt automatisch grijs als
Ollama actief is — `effort` is een Anthropic-feature.

In de "stappen"-strook bovenaan elk antwoord zie je `model: <X>` zodat je
direct kunt verifiëren welke combinatie je vraag heeft beantwoord.

## De hele app op een Raspberry Pi 5 draaien

Je kunt de complete stack (FastAPI backend + statisch geserveerde React UI)
op een Pi 5 draaien via Docker. Co-locatie met Ollama op dezelfde Pi maakt
het hele systeem volledig lokaal.

### Hardware aanbevelingen

- **Pi 5 met 8 GB RAM** — minimum als je naast de webapp ook Ollama wilt
  draaien (`qwen2.5:3b-instruct` heeft ~2.5 GB nodig, de webapp ~300 MB,
  Pi OS zelf ~700 MB; daarmee blijft 4 GB over voor cache en burst-vraag).
  4 GB Pi 5 werkt voor enkel de webapp + cloud Claude, niet voor lokaal LLM.
- **Snelle SD-kaart of NVMe** — `state.db` (SQLite) is klein maar krijgt veel
  schrijfacties tijdens schema-ontdekking. NVMe via de Pi 5 M.2-hat is
  comfortabeler maar niet vereist.

### Stap 1 — Pi OS 64-bit + Docker

```bash
# Pi OS 64-bit Bookworm-Lite is genoeg (geen desktop nodig)
sudo apt update && sudo apt install -y git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker  # of opnieuw inloggen
```

### Stap 2 — Repo klonen en configureren

```bash
git clone https://github.com/ruiterer/HouseDataBrowser.git
cd HouseDataBrowser
cp .env.example .env
nano .env
```

Pas `.env` aan voor de Pi:

- `INFLUX_HOST` → het LAN-IP (of hostname) van je InfluxDB-machine.
- `LLM_PROVIDER` → `claude` (cloud, snelste antwoorden) of `ollama` (volledig
  lokaal). Je kunt later in de UI per vraag wisselen.
- Voor Claude: `ANTHROPIC_API_KEY=sk-ant-...`
- Voor lokaal Ollama op dezelfde Pi: `OLLAMA_HOST=http://172.17.0.1:11434`
  (172.17.0.1 is het Docker-bridge-adres van de host vanuit de container —
  zie ook hieronder).

### Stap 3 — Bouwen en starten

```bash
docker compose up --build -d
docker compose logs -f app
```

De eerste build duurt op een Pi 5 ~5–8 minuten (npm install + Python
dependencies installeren). Daarna boot de container in seconden.

Test: `curl http://<pi-ip>:8000/api/health` → moet `{"status": "ok", ...}`
teruggeven.

Vanaf elke browser op je netwerk: `http://<pi-ip>:8000/`.

### Stap 4 (optioneel) — Ollama op dezelfde Pi co-loceren

Als je volledig lokaal wilt draaien (geen cloud-rondtrip naar Anthropic),
zet Ollama bovenop dezelfde Pi:

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl edit ollama.service
# Voeg toe en sla op:
#   [Service]
#   Environment="OLLAMA_HOST=0.0.0.0:11434"
sudo systemctl restart ollama
ollama pull qwen2.5:3b-instruct
```

Voor `OLLAMA_HOST` in `.env` heb je twee opties:

- **Docker-bridge** (default Docker netwerk): `http://172.17.0.1:11434`. Dit
  werkt zonder extra netwerk-config, omdat 172.17.0.1 vanuit de container het
  host-IP is.
- **`network_mode: host`** in `docker-compose.yml`: dan is `localhost:11434`
  in de container hetzelfde als op de Pi zelf. Eenvoudiger maar de container
  deelt dan het hele host-netwerk.

Aanbeveling: blijf bij de default bridge en gebruik `http://172.17.0.1:11434`.

### Wat te verwachten qua performance

| Wat | Tijd op Pi 5 (CPU) |
|---|---|
| Eerste schema-ontdekking (562 metingen, sequentieel) | ~30–45 sec |
| Volgende vernieuwing (zelfde data) | ~25–40 sec |
| Eenvoudige vraag via Claude (cloud) | ~3–8 sec |
| Eenvoudige vraag via Ollama `qwen2.5:3b` op de Pi | ~15–40 sec |
| Complexe vraag met meerdere queries via Claude `effort=max` | ~20–60 sec |
| Complexe vraag via Ollama `qwen2.5:3b` | vaak onbruikbaar — kies een 7B+ model of wissel naar Claude |

De webapp zelf is razendsnel (de bottleneck zit altijd bij de LLM en de
InfluxDB). De Pi gebruikt onder normale belasting ~5% CPU; alleen Ollama
zelf piekt naar 100% tijdens generatie.

### Updaten

```bash
cd ~/HouseDataBrowser
git pull
docker compose up --build -d
```

Schemacache, gesprekken, en vastgezette grafieken (`./data/state.db`)
overleven een rebuild — de volume-mount in `docker-compose.yml` regelt dat.

## Pi-only-Ollama (webapp elders)

Als je de webapp op je Mac/desktop laat draaien en alleen Ollama op de Pi wilt
hosten, doe stap 4 uit "De hele app op een Raspberry Pi 5 draaien" hierboven
voor de Ollama-installatie, en zet in `.env` op je Mac:

```env
LLM_PROVIDER=ollama          # Of houd 'claude' en kies Ollama in de UI
OLLAMA_HOST=http://pi.local:11434
OLLAMA_MODEL=qwen2.5:3b-instruct
```

Vanaf nu kun je in de UI vrij wisselen: een snelle vraag via Claude, een
gevoelige vraag via Ollama op de Pi.

### AI Hat+ 2

De Hailo-accelerator op de AI Hat+ 2 is geweldig voor vision-modellen, maar
er is nog geen volwassen pipeline om er moderne tool-calling-LLMs op te
draaien. Ollama gebruikt de Pi-CPU; de Hat blijft beschikbaar voor andere
taken.

## Projectopzet

```
backend/
  app/
    config.py            # Pydantic settings, .env-gestuurd
    influx/
      safety.py          # Read-only InfluxQL gate (de security boundary)
      client.py          # Async wrapper over influxdb-python (v1)
      schema_discovery.py# SHOW MEASUREMENTS / TAG KEYS / FIELD KEYS / TAG VALUES
    llm/
      provider.py        # Stabiele Protocol — keep backwards-compatible
      claude.py          # Anthropic SDK + adaptive thinking + prompt caching
      ollama.py          # Native /api/chat with tool calling
      factory.py         # Picks provider from settings (used by registry)
      registry.py        # Houdt beide providers in geheugen voor UI-switching
    agent/
      system_prompt.py   # Composer (Dutch + cached schema overview)
      tools.py           # get_schema_for, run_influxql, render_response
      loop.py            # Heart of the agent; streaming events
    api/
      chat.py            # SSE streaming, conversation persistence
      health.py
      schema.py
      pins.py            # Dashboard pinning
      providers.py       # Lijst van beschikbare LLM-providers + modellen
      results.py
    state/
      models.py          # Conversation, ConversationMessage, PinnedChart, ...
      db.py              # SQLite engine (WAL mode)
      results.py         # In-memory result cache, TTL'd
    main.py              # FastAPI app + lifespan
  tests/test_safety.py   # 28 InfluxQL safety filter tests
frontend/
  src/
    pages/               # Chat, Dashboard, Schema
    components/          # ChartRenderer, DataTable, ChatThread, PinButton,
                         # ProviderPicker, ...
.env.example
Dockerfile               # Multi-stage: node build -> python runtime
docker-compose.yml
```

## Veiligheid

- Alle InfluxQL passeert `app/influx/safety.py` voordat hij InfluxDB raakt.
  Alleen `SELECT`, `SHOW`, en `EXPLAIN` zijn toegestaan; `DROP`, `DELETE`,
  `INSERT`, `CREATE`, `ALTER`, `GRANT`, `REVOKE`, `KILL`, `SET` worden
  geweigerd.
- Multi-statement queries worden geweigerd (geen SQL-injection via `;`).
- `SELECT`-queries krijgen automatisch een `LIMIT` toegevoegd als die ontbreekt
  (default 50.000 rijen).
- Voor extra zekerheid: configureer de `INFLUX_USERNAME` als read-only
  InfluxDB-account.

## Architectonische notities

- **Schema-RAG?** Niet nodig. Bij 562 metingen passen alle namen +
  beschrijvingen in ~15 K tokens, en die strook gaat door de prompt-cache
  van Anthropic (~10× goedkoper). De agent vraagt tag/veld-details on-demand
  via `get_schema_for`.
- **Vastgezette grafieken**: opgeslagen InfluxQL + chart-spec, niet de data.
  Bij elk laden runt elke tegel zijn query opnieuw — actueel én klein op disk.
- **Agent-historie**: assistent-beurten worden samengevouwen tot
  samenvatting + InfluxQL-query bij follow-ups, zodat we tool_use-blokken
  niet hoeven mee te sturen (Anthropic eist anders directe tool_result-blokken
  erna).

## Licentie

MIT — zie [LICENSE](LICENSE).
