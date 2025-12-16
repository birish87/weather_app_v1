"""
FastAPI entrypoint.

This file focuses on:
- routing
- request/response handling
- wiring together DB + clients + templates
"""

from __future__ import annotations

from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session
import json

from .settings import settings
from .db import Base, engine, get_db
from . import models
from .schemas import RecordCreate, RecordUpdate
from .weather_clients import OpenWeatherClient, OpenMeteoClient, WeatherError
from .crud import create_record, list_records, get_record, update_record, delete_record
from .exporters import export_json, export_csv, export_markdown
from urllib.parse import quote_plus

# Create tables automatically (simple for assessments).
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)

# Static and template directories for minimal UI.
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# API clients (constructed once).
owm = OpenWeatherClient(settings.openweather_api_key)
om = OpenMeteoClient()


def record_to_dict(model: models.WeatherQuery) -> dict:
    """Convert ORM model -> dict for JSON/templates/export."""
    return {
        "id": model.id,
        "location_input": model.location_input,
        "resolved_name": model.resolved_name,
        "country": model.country,
        "state": model.state,
        "lat": model.lat,
        "lon": model.lon,
        "start_date": model.start_date,
        "end_date": model.end_date,
        "daily_temps": json.loads(model.daily_temps_json or "[]"),
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


# -------------------------
# UI routes
# -------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Landing page with search + geolocation + CRUD create form."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "candidate_name": settings.candidate_name,
        },
    )


@app.get("/results", response_class=HTMLResponse)
async def results_page(request: Request, q: str = Query(..., min_length=2, max_length=255)):
    """
    Server-rendered weather result page.
    - geocode -> lat/lon
    - current weather
    - 5-day forecast summarized to daily cards
    - link to YouTube search for location
    """
    try:
        resolved = await owm.geocode(q)
        youtube_query = quote_plus(f"{resolved.name} {resolved.state} {resolved.country}".strip())
        youtube_url = f"https://www.youtube.com/results?search_query={youtube_query}"
        current = await owm.current_weather(resolved.lat, resolved.lon, units="imperial")
        forecast_raw = await owm.forecast_5day_3h(resolved.lat, resolved.lon, units="imperial")
        five_day = owm.summarize_to_5_days(forecast_raw)
    except WeatherError as e:
        return templates.TemplateResponse(
            "results.html",
            {"request": request, "error": str(e), "q": q, "candidate_name": settings.candidate_name},
            status_code=400,
        )

    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "q": q,
            "resolved": resolved,
            "current": current,
            "five_day": five_day,
            "candidate_name": settings.candidate_name,
            "forecast_3h": forecast_raw,
            "youtube_url": youtube_url
        },
    )


@app.get("/records", response_class=HTMLResponse)
async def records_page(request: Request, db: Session = Depends(get_db)):
    """List saved records."""
    records = [record_to_dict(r) for r in list_records(db)]
    return templates.TemplateResponse("records.html", {"request": request, "records": records})


@app.get("/records/{record_id}", response_class=HTMLResponse)
async def record_detail_page(request: Request, record_id: int, db: Session = Depends(get_db)):
    """Show one record and its stored daily temps."""
    r = get_record(db, record_id)
    if not r:
        raise HTTPException(status_code=404, detail="Record not found")
    return templates.TemplateResponse("record_detail.html", {"request": request, "record": record_to_dict(r)})


# -------------------------
# Assessment 1 APIs
# -------------------------

@app.get("/api/weather")
async def api_weather(q: str = Query(..., min_length=2, max_length=255)):
    """
    Location-based weather (Assessment 1):
    - current weather
    - 5-day forecast
    - icon codes returned by OpenWeather
    """
    try:
        resolved = await owm.geocode(q)
        current = await owm.current_weather(resolved.lat, resolved.lon, units="imperial")
        forecast_raw = await owm.forecast_5day_3h(resolved.lat, resolved.lon, units="imperial")
        five_day = owm.summarize_to_5_days(forecast_raw)
        return {"resolved": resolved.__dict__, "current": current, "five_day": five_day}
    except WeatherError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/weather/by-coords")
async def api_weather_by_coords(lat: float, lon: float):
    """
    Current-location weather (Assessment 1 "stand out"):
    - browser provides coords via Geolocation API
    - server returns current + 5-day forecast
    """
    try:
        current = await owm.current_weather(lat, lon, units="imperial")
        forecast_raw = await owm.forecast_5day_3h(lat, lon, units="imperial")
        five_day = owm.summarize_to_5_days(forecast_raw)
        resolved = await owm.geocode(f"{lat},{lon}")

        return {
            "resolved": resolved.__dict__,
            "current": current,
            "five_day": five_day,
            "forecast_3h": forecast_raw,
        }
    except WeatherError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------
# Assessment 2 CRUD APIs
# -------------------------

@app.post("/api/records")
async def api_create_record(payload: RecordCreate, db: Session = Depends(get_db)):
    """Create a stored date-range query."""
    try:
        rec = await create_record(db, payload, owm, om)
        return record_to_dict(rec)
    except WeatherError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/records")
def api_list_records(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    """List records with pagination."""
    recs = list_records(db, limit=limit, offset=offset)
    return [record_to_dict(r) for r in recs]


# -------------------------
# Export endpoint
# -------------------------

@app.get("/api/records/export")
def api_export_records(fmt: str = Query("json", pattern="^(json|csv|md)$"), db: Session = Depends(get_db)):
    """Export records to JSON/CSV/Markdown."""
    recs = [record_to_dict(r) for r in list_records(db, limit=1000, offset=0)]
    if fmt == "json":
        return PlainTextResponse(export_json(recs), media_type="application/json")
    if fmt == "csv":
        return PlainTextResponse(export_csv(recs), media_type="text/csv")
    if fmt == "md":
        return PlainTextResponse(export_markdown(recs), media_type="text/markdown")
    raise HTTPException(status_code=400, detail="Unsupported format")


@app.get("/api/records/{record_id}")
def api_get_record(record_id: int, db: Session = Depends(get_db)):
    """Fetch a single record."""
    r = get_record(db, record_id)
    if not r:
        raise HTTPException(status_code=404, detail="Record not found")
    return record_to_dict(r)


@app.put("/api/records/{record_id}")
async def api_update_record(record_id: int, payload: RecordUpdate, db: Session = Depends(get_db)):
    """Update location/date range, re-fetch temps, and persist."""
    r = get_record(db, record_id)
    if not r:
        raise HTTPException(status_code=404, detail="Record not found")
    try:
        updated = await update_record(db, r, payload, owm, om)
        return record_to_dict(updated)
    except WeatherError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/records/{record_id}")
def api_delete_record(record_id: int, db: Session = Depends(get_db)):
    """Delete a record."""
    r = get_record(db, record_id)
    if not r:
        raise HTTPException(status_code=404, detail="Record not found")
    delete_record(db, r)
    return {"ok": True}
