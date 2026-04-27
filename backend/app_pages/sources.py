from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from db import get_db
from models.sources import SourceORM

from pydantic import BaseModel
from typing import Optional, List, Dict, Any

router = APIRouter()


class SourceIn(BaseModel):
    name: str
    traffic_loss: Optional[float] = 0
    s2s_postback: Optional[str] = None
    s2s_postback_statuses: Optional[Dict[str, bool]] = {}
    settings: List[Dict[str, Any]] = []
    additional_settings: Dict[str, Any] = {}


class SourceOut(SourceIn):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


@router.get("/")
def get_sources(
    db: Session = Depends(get_db),
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD")
):
    """Get sources with statistics from clicks_daily_stats."""
    # Default date range: last 30 days
    if not date_to:
        date_to = datetime.utcnow().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    # SQL query to get sources with aggregated statistics
    # Join sources -> campaigns -> clicks_daily_stats
    query = text("""
        SELECT 
            src.id,
            src.name,
            src.traffic_loss,
            src.s2s_postback,
            src.s2s_postback_statuses,
            src.settings,
            src.additional_settings,
            src.group_id,
            src.created_at,
            src.updated_at,
            COALESCE(SUM(s.clicks), 0)::bigint as clicks,
            COALESCE(SUM(s.unique_clicks), 0)::bigint as unique_clicks,
            COALESCE(SUM(s.conversions), 0)::bigint as conversions,
            COALESCE(SUM(s.revenue), 0)::real as revenue,
            COALESCE(SUM(s.cost), 0)::real as cost,
            (COALESCE(SUM(s.revenue), 0) - COALESCE(SUM(s.cost), 0))::real as profit
        FROM sources src
        LEFT JOIN campaigns c ON c.traffic_source_id = src.id
        LEFT JOIN clicks_daily_stats s ON s.campaign_id = c.id
            AND s.date >= :date_from AND s.date <= :date_to
        GROUP BY src.id, src.name, src.traffic_loss, src.s2s_postback, 
                 src.s2s_postback_statuses, src.settings, src.additional_settings, 
                 src.group_id, src.created_at, src.updated_at
        ORDER BY src.id ASC
    """)

    result = db.execute(query, {"date_from": date_from, "date_to": date_to})
    rows = result.fetchall()

    sources = []
    for row in rows:
        clicks = row.clicks or 0
        conversions = row.conversions or 0
        revenue = row.revenue or 0
        cost = row.cost or 0
        profit = row.profit or 0

        # Calculate ROI: (profit / cost) * 100
        roi = (profit / cost * 100) if cost > 0 else 0

        # Calculate CR: (conversions / clicks) * 100
        cr = (conversions / clicks * 100) if clicks > 0 else 0

        sources.append({
            "id": row.id,
            "name": row.name,
            "traffic_loss": row.traffic_loss or 0,
            "s2s_postback": row.s2s_postback,
            "s2s_postback_statuses": row.s2s_postback_statuses or {},
            "settings": row.settings or [],
            "additional_settings": row.additional_settings or {},
            "group_id": row.group_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            # Statistics
            "clicks": clicks,
            "unique_clicks": row.unique_clicks or 0,
            "conversions": conversions,
            "revenue": round(revenue, 2),
            "cost": round(cost, 2),
            "profit": round(profit, 2),
            "roi": round(roi, 2),
            "cr": round(cr, 2)
        })

    return sources


@router.post("/", response_model=SourceOut)
def create_source(payload: SourceIn, db: Session = Depends(get_db)):
    source = SourceORM(**payload.dict())
    db.add(source)
    try:
        db.commit()
        db.refresh(source)
        return source
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Source with this name already exists.")


@router.patch("/{source_id}", response_model=SourceOut)
def update_source(source_id: int, payload: SourceIn, db: Session = Depends(get_db)):
    source = db.query(SourceORM).filter(SourceORM.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    for key, value in payload.dict(exclude_unset=True).items():
        setattr(source, key, value)

    db.commit()
    db.refresh(source)
    return source


@router.delete("/{source_id}")
def delete_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(SourceORM).filter(SourceORM.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    db.delete(source)
    db.commit()
    return {"message": "Source deleted"}
