from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from db import get_db
from models.offers import OfferORM

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

router = APIRouter()

class OfferIn(BaseModel):
    name: str
    url: str
    affiliate_network_id: Optional[int] = None
    countries: Optional[List[Dict[str, Any]]] = []
    payout: Optional[float] = 0
    currency: Optional[str] = "USD"
    status: Optional[str] = "active"
    tokens: Optional[Dict[str, Any]] = {}
    notes: Optional[str] = ''
    tags: Optional[List[str]] = []

class OfferOut(OfferIn):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


@router.get("/")
def get_offers(
    db: Session = Depends(get_db),
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD")
):
    """Get offers with statistics from clicks_daily_stats."""
    # Default date range: last 30 days
    if not date_to:
        date_to = datetime.utcnow().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    # SQL query to get offers with aggregated statistics
    query = text("""
        SELECT 
            o.id,
            o.name,
            o.url,
            o.affiliate_network_id,
            o.countries,
            o.payout,
            o.currency,
            o.status,
            o.tokens,
            o.notes,
            o.tags,
            o.group_id,
            o.created_at,
            o.updated_at,
            COALESCE(SUM(s.clicks), 0)::bigint as clicks,
            COALESCE(SUM(s.unique_clicks), 0)::bigint as unique_clicks,
            COALESCE(SUM(s.conversions), 0)::bigint as conversions,
            COALESCE(SUM(s.revenue), 0)::real as revenue,
            COALESCE(SUM(s.cost), 0)::real as cost,
            (COALESCE(SUM(s.revenue), 0) - COALESCE(SUM(s.cost), 0))::real as profit
        FROM offers o
        LEFT JOIN clicks_daily_stats s ON s.offer_id = o.id
            AND s.date >= :date_from AND s.date <= :date_to
        GROUP BY o.id, o.name, o.url, o.affiliate_network_id, o.countries, 
                 o.payout, o.currency, o.status, o.tokens, o.notes, o.tags, 
                 o.group_id, o.created_at, o.updated_at
        ORDER BY o.id DESC
    """)

    result = db.execute(query, {"date_from": date_from, "date_to": date_to})
    rows = result.fetchall()

    offers = []
    for row in rows:
        clicks = row.clicks or 0
        conversions = row.conversions or 0
        revenue = row.revenue or 0
        cost = row.cost or 0
        profit = row.profit or 0

        # Calculate CR: (conversions / clicks) * 100
        cr = (conversions / clicks * 100) if clicks > 0 else 0

        # Calculate EPC: revenue / clicks
        epc = (revenue / clicks) if clicks > 0 else 0

        # Calculate ROI: (profit / cost) * 100
        roi = (profit / cost * 100) if cost > 0 else 0

        offers.append({
            "id": row.id,
            "name": row.name,
            "url": row.url,
            "affiliate_network_id": row.affiliate_network_id,
            "countries": row.countries or [],
            "payout": float(row.payout) if row.payout else 0,
            "currency": row.currency,
            "status": row.status,
            "tokens": row.tokens or {},
            "notes": row.notes,
            "tags": row.tags or [],
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
            "cr": round(cr, 2),
            "epc": round(epc, 4),
            "roi": round(roi, 2)
        })

    return offers

@router.post("/")
def create_offer(offer: OfferIn, db: Session = Depends(get_db)):
    new_offer = OfferORM(**offer.dict())
    db.add(new_offer)
    try:
        db.commit()
        db.refresh(new_offer)
        return {"message": "Offer created", "id": new_offer.id}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Offer with this name already exists")

@router.patch("/{offer_id}")
def update_offer(offer_id: int, offer: OfferIn, db: Session = Depends(get_db)):
    db_offer = db.query(OfferORM).filter_by(id=offer_id).first()
    if not db_offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    for key, value in offer.dict().items():
        setattr(db_offer, key, value)

    db.commit()
    return {"message": "Offer updated"}

@router.delete("/{offer_id}")
def delete_offer(offer_id: int, db: Session = Depends(get_db)):
    db_offer = db.query(OfferORM).filter_by(id=offer_id).first()
    if not db_offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    db.delete(db_offer)
    db.commit()
    return {"message": "Offer deleted"}
