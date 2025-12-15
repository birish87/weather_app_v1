"""
Pydantic schemas.

Why:
- Validation (e.g., strings not empty, correct types)
- Defines the contract of our REST endpoints
"""

from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import List, Optional, Any


class GeoResolved(BaseModel):
    """Normalized location data returned by geocoding."""
    name: str
    country: str = ""
    state: str = ""
    lat: float
    lon: float


class DailyTemp(BaseModel):
    """One day of temperature data stored for Assessment 2."""
    date: date
    tmin: float
    tmax: float


class RecordCreate(BaseModel):
    """
    Payload for creating a stored record:
    location + date range.
    """
    location: str = Field(..., min_length=2, max_length=255)
    start_date: date
    end_date: date


class RecordUpdate(BaseModel):
    """
    Updates allow changing location and/or date range.
    If anything changes we re-fetch temps and re-store.
    """
    location: Optional[str] = Field(None, min_length=2, max_length=255)
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class RecordOut(BaseModel):
    """
    Record representation returned from the API.
    Useful for exporting or displaying details in the UI.
    """
    id: int
    location_input: str
    resolved_name: str
    country: str
    state: str
    lat: float
    lon: float
    start_date: date
    end_date: date
    daily_temps: List[DailyTemp]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CurrentWeatherOut(BaseModel):
    """
    Output structure for current + forecast weather calls.
    current/five_day are loosely typed (OpenWeather payload shapes),
    which keeps this implementation simple and robust.
    """
    resolved: GeoResolved
    current: Any
    five_day: Any
