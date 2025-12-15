"""
CRUD functions.

Why keep CRUD separate from main.py?
- main.py stays readable (routing + request/response)
- CRUD functions become easy to unit test
- Central place for validations (date range rules, location resolution, etc.)
"""

from __future__ import annotations

from sqlalchemy.orm import Session
from datetime import date, datetime
import json

from . import models
from .schemas import RecordCreate, RecordUpdate
from .weather_clients import OpenWeatherClient, OpenMeteoClient, WeatherError


# A small cap prevents people from requesting huge date ranges,
# keeps API calls fast, and avoids storing overly large blobs in SQLite.
MAX_RANGE_DAYS = 16


def validate_date_range(start: date, end: date) -> None:
    """
    Business rule validations for date ranges.
    """
    if end < start:
        raise WeatherError("Invalid date range: end_date must be >= start_date.")

    delta_days = (end - start).days
    if delta_days > MAX_RANGE_DAYS:
        raise WeatherError(f"Date range too large. Please use <= {MAX_RANGE_DAYS} days.")


async def create_record(db: Session, payload: RecordCreate, owm: OpenWeatherClient, om: OpenMeteoClient) -> models.WeatherQuery:
    """
    CREATE record:
    - validate date range
    - validate location exists (geocode)
    - fetch daily temps for range
    - store in DB
    """
    validate_date_range(payload.start_date, payload.end_date)

    resolved = await owm.geocode(payload.location)
    temps = await om.daily_temps(resolved.lat, resolved.lon, payload.start_date, payload.end_date)

    now = datetime.utcnow()
    record = models.WeatherQuery(
        location_input=payload.location,
        resolved_name=resolved.name,
        country=resolved.country,
        state=resolved.state,
        lat=resolved.lat,
        lon=resolved.lon,
        start_date=payload.start_date,
        end_date=payload.end_date,
        daily_temps_json=json.dumps(temps),
        created_at=now,
        updated_at=now,
    )

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_records(db: Session, limit: int = 100, offset: int = 0):
    """List records with basic pagination."""
    return (
        db.query(models.WeatherQuery)
        .order_by(models.WeatherQuery.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_record(db: Session, record_id: int) -> models.WeatherQuery | None:
    """Fetch a single record by id."""
    return db.query(models.WeatherQuery).filter(models.WeatherQuery.id == record_id).first()


async def update_record(db: Session, record: models.WeatherQuery, payload: RecordUpdate, owm: OpenWeatherClient, om: OpenMeteoClient) -> models.WeatherQuery:
    """
    UPDATE record:
    - determine updated values
    - validate date range
    - re-geocode location if changed
    - re-fetch daily temps for new values
    - persist
    """
    location = payload.location if payload.location is not None else record.location_input
    start = payload.start_date if payload.start_date is not None else record.start_date
    end = payload.end_date if payload.end_date is not None else record.end_date

    validate_date_range(start, end)

    resolved = await owm.geocode(location)
    temps = await om.daily_temps(resolved.lat, resolved.lon, start, end)

    record.location_input = location
    record.resolved_name = resolved.name
    record.country = resolved.country
    record.state = resolved.state
    record.lat = resolved.lat
    record.lon = resolved.lon
    record.start_date = start
    record.end_date = end
    record.daily_temps_json = json.dumps(temps)
    record.updated_at = datetime.utcnow()

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def delete_record(db: Session, record: models.WeatherQuery) -> None:
    """DELETE record."""
    db.delete(record)
    db.commit()
