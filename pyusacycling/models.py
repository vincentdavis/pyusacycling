"""
Pydantic models for the USA Cycling Results Parser package.
"""
from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, HttpUrl, validator


class Address(BaseModel):
    """Model for a physical address."""
    street: Optional[str] = None
    street2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    class Config:
        """Pydantic model configuration."""
        frozen = True


class EventDate(BaseModel):
    """Model for an event date with location."""
    date_id: Optional[str] = None
    description: Optional[str] = None
    start_date: date
    end_date: date
    address: Optional[Address] = None
    
    class Config:
        """Pydantic model configuration."""
        frozen = True


class EventType(str, Enum):
    """Enum for event types."""
    ROAD = "road"
    MOUNTAIN = "mountain"
    CYCLOCROSS = "cyclocross"
    TRACK = "track"
    BMX = "bmx"
    GRAVEL = "gravel"
    OTHER = "other"


class EventLinks(BaseModel):
    """Model for event-related links."""
    logo_url: Optional[HttpUrl] = None
    badge_url: Optional[HttpUrl] = None
    register_url: Optional[HttpUrl] = None
    website_url: Optional[HttpUrl] = None
    social_urls: List[Dict[str, str]] = Field(default_factory=list)
    
    class Config:
        """Pydantic model configuration."""
        frozen = True


class ApiEvent(BaseModel):
    """Model for an event from the USA Cycling API."""
    event_id: str
    name: str
    start_date: date
    end_date: date
    dates: List[EventDate] = Field(default_factory=list)
    is_featured: bool = False
    is_weekend: bool = False
    is_multiday: bool = False
    is_usac_sanctioned: bool = False
    event_organizer_email: Optional[str] = None
    event_status: str
    permit: str
    labels: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    links: Optional[EventLinks] = None
    data_source: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        """Pydantic model configuration."""
        frozen = True
    
    @classmethod
    @validator('start_date', 'end_date', pre=True)
    def parse_date(cls, value: Any) -> date:
        """Parse date from string if needed."""
        if isinstance(value, str):
            return datetime.strptime(value, "%Y-%m-%d").date()
        return value  # type: ignore


class EventSearchResponse(BaseModel):
    """Model for the event search API response."""
    data: List[ApiEvent] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        """Pydantic model configuration."""
        frozen = True


class Event(BaseModel):
    """Model for a USA Cycling event (simplified version)."""
    id: str
    name: str
    permit_number: str
    date: date
    location: str
    state: str
    year: int
    event_type: Optional[EventType] = None
    url: Optional[str] = None
    
    class Config:
        """Pydantic model configuration."""
        frozen = True


class EventDetails(BaseModel):
    """Model for detailed event information."""
    id: str
    name: str
    permit_number: str
    start_date: date
    end_date: date
    location: str
    state: str
    year: int
    event_type: Optional[EventType] = None
    promoter: Optional[str] = None
    promoter_email: Optional[str] = None
    website: Optional[str] = None
    registration_url: Optional[str] = None
    is_usac_sanctioned: bool = False
    categories: Any = Field(default_factory=list)
    disciplines: List[Dict[str, str]] = Field(default_factory=list)
    description: Optional[str] = None
    dates: List[EventDate] = Field(default_factory=list)
    
    class Config:
        """Pydantic model configuration."""
        frozen = True


class RaceCategory(BaseModel):
    """Model for a race category."""
    id: str
    name: str
    event_id: str
    race_date: Optional[date] = None
    distance: Optional[str] = None
    participants_count: Optional[int] = None
    category_type: Optional[str] = None
    discipline: Optional[str] = None
    gender: Optional[str] = None
    age_range: Optional[str] = None
    category_rank: Optional[str] = None
    
    class Config:
        """Pydantic model configuration."""
        frozen = True


class RaceTime(BaseModel):
    """Model for race timing information."""
    raw_time: Optional[str] = None
    formatted_time: Optional[str] = None
    seconds: Optional[float] = None
    gap_to_leader: Optional[str] = None
    
    class Config:
        """Pydantic model configuration."""
        frozen = True


class RiderResult(BaseModel):
    """Model for a single rider's result in a race."""
    place: str
    place_number: Optional[int] = None
    is_dnf: bool = False
    is_dns: bool = False
    is_dq: bool = False
    points: Optional[int] = None
    premium_points: Optional[int] = None
    time: Optional[RaceTime] = None
    
    class Config:
        """Pydantic model configuration."""
        frozen = True


class Rider(BaseModel):
    """Model for a race participant."""
    place: str
    name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    team: Optional[str] = None
    team_id: Optional[str] = None
    license: Optional[str] = None
    license_type: Optional[str] = None
    racing_age: Optional[int] = None
    bib: Optional[str] = None
    time: Optional[str] = None
    result: Optional[RiderResult] = None
    
    class Config:
        """Pydantic model configuration."""
        frozen = True
    
    @classmethod
    @validator('place', pre=True)
    def parse_place(cls, value: Any) -> str:
        """Convert place to string and handle special cases."""
        if value is None:
            return "N/A"
        return str(value)


class RaceLap(BaseModel):
    """Model for a lap in a race."""
    lap_number: int
    rider_id: str
    time: Optional[str] = None
    elapsed_time: Optional[str] = None
    seconds: Optional[float] = None
    
    class Config:
        """Pydantic model configuration."""
        frozen = True


class RaceResult(BaseModel):
    """Model for race results."""
    id: str
    event_id: str
    # category: Optional[RaceCategory] = None
    date: date
    start_time: Optional[datetime] = None
    total_laps: Optional[int] = None
    total_distance: Optional[str] = None
    weather_conditions: Optional[str] = None
    course_description: Optional[str] = None
    riders: List[Rider] = Field(default_factory=list)
    laps: List[RaceLap] = Field(default_factory=list)
    has_time_data: bool = False
    has_lap_data: bool = False
    
    class Config:
        """Pydantic model configuration."""
        frozen = True


class RaceSeriesStanding(BaseModel):
    """Model for a rider's standing in a race series."""
    series_id: str
    series_name: str
    rider_id: str
    rider_name: str
    position: int
    total_points: int
    races_completed: int
    category: Optional[str] = None
    team: Optional[str] = None
    
    class Config:
        """Pydantic model configuration."""
        frozen = True


class SeriesResults(BaseModel):
    """Model for results of a race series."""
    id: str
    name: str
    year: int
    categories: List[str] = Field(default_factory=list)
    events: List[str] = Field(default_factory=list)
    standings: List[RaceSeriesStanding] = Field(default_factory=list)
    
    class Config:
        """Pydantic model configuration."""
        frozen = True
