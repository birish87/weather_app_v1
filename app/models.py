"""
ORM models.

We store:
- user input location string
- resolved lat/lon + resolved place name (so the record is stable)
- requested date range
- returned daily temperatures (JSON serialized)
"""

from sqlalchemy import String, Integer, Float, Date, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from .db import Base


class WeatherQuery(Base):
    __tablename__ = "weather_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # What the user typed (keep it for auditability / UX)
    location_input: Mapped[str] = mapped_column(String(255), index=True)

    # Geocoded/normalized location details
    resolved_name: Mapped[str] = mapped_column(String(255))
    country: Mapped[str] = mapped_column(String(32), default="")
    state: Mapped[str] = mapped_column(String(64), default="")
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)

    # Date range the user requested (Assessment 2 "create" requirement)
    start_date: Mapped[datetime.date] = mapped_column(Date)
    end_date: Mapped[datetime.date] = mapped_column(Date)

    # Stored daily temperature results as a JSON string.
    # Example:
    #   [{"date":"2025-12-10","tmin":2.1,"tmax":6.2}, ...]
    daily_temps_json: Mapped[str] = mapped_column(Text)

    # Timestamps (nice for CRUD audit and sorting)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
