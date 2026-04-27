from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from db import get_db
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

router = APIRouter()


class LandingIn(BaseModel):
    name: str
    url: Optional[str] = None
    offer_id: Optional[int] = None
    group_id: Optional[int] = None
    status: Optional[str] = "active"
    notes: Optional[str] = ""


class LandingOut(LandingIn):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


@router.get("/")
def get_landings(
    db: Session = Depends(get_db),
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD")
):
    """Get landings with statistics from clicks_daily_stats."""
    # Default date range: last 30 days
    if not date_to:
        date_to = datetime.utcnow().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    # SQL query to get landings with aggregated statistics
    query = text("""
        SELECT 
            l.id,
            l.name,
            l.url,
            l.offer_id,
            l.group_id,
            l.state as status,
            l.action_type,
            l.action_payload,
            l.created_at,
            l.updated_at,
            COALESCE(SUM(s.clicks), 0)::bigint as clicks,
            COALESCE(SUM(s.unique_clicks), 0)::bigint as unique_clicks,
            COALESCE(SUM(s.conversions), 0)::bigint as conversions,
            COALESCE(SUM(s.revenue), 0)::real as revenue,
            COALESCE(SUM(s.cost), 0)::real as cost,
            (COALESCE(SUM(s.revenue), 0) - COALESCE(SUM(s.cost), 0))::real as profit
        FROM landings l
        LEFT JOIN clicks_daily_stats s ON s.landing_id = l.id
            AND s.date >= :date_from AND s.date <= :date_to
        WHERE l.state IS NULL OR l.state != 'deleted'
        GROUP BY l.id, l.name, l.url, l.offer_id, l.group_id, l.state, 
                 l.action_type, l.action_payload, l.created_at, l.updated_at
        ORDER BY l.id DESC
    """)

    try:
        result = db.execute(query, {"date_from": date_from, "date_to": date_to})
        rows = result.fetchall()
    except Exception as e:
        # If landings table doesn't exist, return empty list
        print(f"Error fetching landings: {e}")
        return []

    landings = []
    for row in rows:
        clicks = row.clicks or 0
        conversions = row.conversions or 0
        cost = row.cost or 0
        profit = row.profit or 0
        
        roi = round((profit / cost) * 100, 2) if cost > 0 else 0
        cr = round((conversions / clicks) * 100, 2) if clicks > 0 else 0

        landings.append({
            "id": row.id,
            "name": row.name,
            "url": row.url,
            "offer_id": row.offer_id,
            "group_id": row.group_id,
            "status": row.status or "active",
            "action_type": row.action_type,
            "action_payload": row.action_payload,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "clicks": clicks,
            "unique_clicks": row.unique_clicks or 0,
            "conversions": conversions,
            "revenue": round(row.revenue or 0, 2),
            "cost": round(cost, 2),
            "profit": round(profit, 2),
            "roi": roi,
            "cr": cr
        })

    return landings


@router.get("/{landing_id}")
def get_landing(landing_id: int, db: Session = Depends(get_db)):
    """Get a single landing by ID."""
    query = text("""
        SELECT id, name, url, offer_id, group_id, state as status,
               action_type, action_payload, created_at, updated_at
        FROM landings
        WHERE id = :landing_id
    """)
    
    result = db.execute(query, {"landing_id": landing_id})
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Landing not found")
    
    return {
        "id": row.id,
        "name": row.name,
        "url": row.url,
        "offer_id": row.offer_id,
        "group_id": row.group_id,
        "status": row.status or "active",
        "action_type": row.action_type,
        "action_payload": row.action_payload,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None
    }