# HouseDataBrowser

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

## Status: alle 5 fases werkend

- ✅ Fase 1 — backend + frontend skeleton, InfluxQL safety filter (28 tests groen)
- ✅ Fase 2 — schema-ontdekking + Schema-pagina met bewerkbare beschrijvingen
- ✅ Fase 3 — LLM-agent-loop met streaming SSE, Plotly-grafieken, debug-paneel,
  per-vraag "Diep nadenken"-knop, Nederlandse UI
- ✅ Fase 4 — vastgezette grafieken op een sleepbaar Dashboard (queries blijven
  vers omdat ze opnieuw gedraaid worden bij het laden)
- ✅ Fase 5 — Ollama-provider met tool-calling voor lokale modellen

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

## Lokaal LLM op een Raspberry Pi 5 + AI Hat+ 2

De agent praat met elke LLM-aanbieder via dezelfde `LLMProvider`-interface
(`backend/app/llm/provider.py`). Switchen tussen Claude en Ollama is één
env-variabele, geen herbouw.

### Ollama op de Pi opzetten

1. **Installeer Ollama** op de Pi (Pi OS 64-bit, 8 GB RAM aanbevolen):

   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Stel hem bloot aan je LAN** zodat het HouseDataBrowser-Docker-container
   hem kan bereiken (default luistert Ollama alleen op localhost):

   ```bash
   sudo systemctl edit ollama.service
   # Voeg toe:
   #   [Service]
   #   Environment="OLLAMA_HOST=0.0.0.0:11434"
   sudo systemctl restart ollama
   ```

3. **Trek een tool-calling model**. Aanbevelingen voor de Pi 5 (CPU, geen GPU):

   | Model | Grootte | Tool-use kwaliteit | Geheugen |
   |---|---|---|---|
   | `qwen2.5:3b-instruct` | 1.9 GB | Goed | ~2.5 GB |
   | `qwen2.5:7b-instruct` | 4.4 GB | Heel goed | ~5.5 GB |
   | `llama3.1:8b-instruct-q4_K_M` | 4.9 GB | Goed | ~6 GB |

   ```bash
   ollama pull qwen2.5:3b-instruct
   ```

   Kleinere modellen passen in 4 GB RAM maar zijn merkbaar minder goed in
   tool-calling. Begin met `qwen2.5:3b-instruct` en upgrade als nodig.

4. **Test vanaf je Mac** dat Ollama bereikbaar is:

   ```bash
   curl http://pi.local:11434/api/tags
   ```

### HouseDataBrowser naar de Pi laten wijzen

Pas in `.env` aan:

```env
LLM_PROVIDER=ollama
OLLAMA_HOST=http://pi.local:11434
OLLAMA_MODEL=qwen2.5:3b-instruct
```

Herstart de backend (uvicorn `--reload` pakt de wijziging op). De badge
rechtsboven verandert naar `influx ✓ · ollama` en de "stappen"-strook bovenaan
elk antwoord toont nu `model: qwen2.5:3b-instruct`.

### Wat te verwachten

- **Snelheid**: een eenvoudige vraag op `qwen2.5:3b-instruct` op een Pi 5 duurt
  ~10-30 seconden (versus ~5 sec op Claude). De `Diep nadenken`-knop heeft op
  Ollama geen effect — `effort` is een Anthropic-feature.
- **Kwaliteit**: kleinere modellen kunnen vragen vertalen die exact één meting
  raken. Voor complexe vragen (multi-meting joins, ambigue intentie) is Claude
  duidelijk sterker. Voor de meeste alledaagse vragen volstaat een Pi-model.
- **AI Hat+ 2**: de Hailo-accelerator is geweldig voor vision, maar er is nog
  geen volwassen LLM-pipeline voor. Ollama draait op de Pi-CPU; de Hat is
  reserveerbaar voor andere taken.

### Tussen providers wisselen tijdens gebruik

Verander gewoon `LLM_PROVIDER` en herstart de backend. Bestaande gesprekken
worden gewoon opgepakt door de nieuwe provider — alleen de tekstsamenvatting +
InfluxQL gaan terug in de geschiedenis (niet de tool-call-trace), dus
follow-ups blijven coherent.

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
      factory.py         # Picks provider from settings
    agent/
      system_prompt.py   # Composer (Dutch + cached schema overview)
      tools.py           # get_schema_for, run_influxql, render_response
      loop.py            # Heart of the agent; streaming events
    api/
      chat.py            # SSE streaming, conversation persistence
      health.py
      schema.py
      pins.py            # Dashboard pinning
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
    components/          # ChartRenderer, DataTable, ChatThread, PinButton, ...
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
