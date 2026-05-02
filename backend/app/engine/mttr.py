"""MTTR (Mean Time To Repair) calculation utilities."""
from datetime import datetime


def calculate_mttr_minutes(incident_start: datetime, incident_end: datetime) -> float:
    """
    Calculate MTTR in minutes.
    MTTR = Time from first signal to RCA submission (end_time).
    """
    if incident_end <= incident_start:
        raise ValueError("incident_end must be after incident_start")
    delta = incident_end - incident_start
    return round(delta.total_seconds() / 60, 2)


def format_mttr(mttr_minutes: float) -> str:
    """Human-readable MTTR string."""
    if mttr_minutes < 1:
        return f"{int(mttr_minutes * 60)}s"
    if mttr_minutes < 60:
        return f"{int(mttr_minutes)}m {int((mttr_minutes % 1) * 60)}s"
    hours = int(mttr_minutes // 60)
    minutes = int(mttr_minutes % 60)
    return f"{hours}h {minutes}m"
