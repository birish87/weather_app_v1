# Weather App - Tech Assessments 1 & 2 (Includes 2.1, 2.2, & 2.3)

Implements:

## Assessment 1
- User-entered location -> current weather (real API)
- 5-day forecast (summarized to daily cards)
- Current-location weather via browser geolocation
- Weather icons

## Assessment 2
- SQLite persistence + CRUD
- Create: user enters location + date range
  - validates date range
  - validates location exists (geocoding)
  - fetches daily temps for the range
  - stores results in SQLite
- Read / Update / Delete records
- Export records to JSON / CSV / Markdown
- YouTube and Google Maps integration

### API Choices
- OpenWeatherMap:
  - Geocoding (location -> lat/lon)
  - Current weather
  - 5-day forecast (3-hour increments, then summarized)
- Open-Meteo (no API key needed):
  - Daily min/max temps for a requested date range
  - Used for the "CRUD date-range temperature storage" requirement
- Nominatim
  - for landmark data lookup

## Setup

1) Create venv + install deps:
```bash
python -m venv .venv
source .venv/bin/activate   # windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2) Create `.env` from `.env.example` and add OPENWEATHER_API_KEY (enclosed in my email).
```bash
cp .env.example .env
# set OPENWEATHER_API_KEY
```

3) Run:
```bash
uvicorn app.main:app --reload
```

Open: http://127.0.0.1:8000

## Quick API tests

### Assessment 1
```bash
curl "http://127.0.0.1:8000/api/weather?q=Austin,TX%20US"
```

### Assessment 2 create record
```bash
curl -X POST "http://127.0.0.1:8000/api/records" \
  -H "Content-Type: application/json" \
  -d '{"location":"Dallas, TX US","start_date":"2025-12-10","end_date":"2025-12-15"}'
```

### Export
```bash
curl "http://127.0.0.1:8000/api/records/export?fmt=json"
curl "http://127.0.0.1:8000/api/records/export?fmt=csv"
curl "http://127.0.0.1:8000/api/records/export?fmt=md"
```
