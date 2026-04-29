from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from db import get_db
from models.campaigns import CampaignORM
from typing import List

from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime, timedelta

router = APIRouter()

class CampaignIn(BaseModel):
    name: str
    alias: str
    type: Literal['campaign', 'tracking_only'] = 'campaign'
    status: Literal['active', 'paused', 'archived'] = 'active'
    redirect_mode: Literal['position', 'weight'] = 'position'
    traffic_source_id: Optional[int] = None
    domain_id: Optional[int] = None
    notes: Optional[str] = None
    config: Optional[dict] = None

class CampaignOut(CampaignIn):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


@router.get("/")
def get_campaigns(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Search by campaign name"),
    group_id: Optional[int] = Query(None, description="Filter by group ID"),
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD")
):
    """Get campaigns with statistics from clicks_daily_stats."""
    # Default date range: last 30 days
    if not date_to:
        date_to = datetime.utcnow().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    # Build WHERE clause for filters
    where_clauses = ["1=1"]
    params = {"date_from": date_from, "date_to": date_to}
    
    if search:
        where_clauses.append("c.name ILIKE :search")
        params["search"] = f"%{search}%"
    
    if group_id:
        where_clauses.append("c.group_id = :group_id")
        params["group_id"] = group_id
    
    where_sql = " AND ".join(where_clauses)

    # SQL query to get campaigns with aggregated statistics
    query = text(f"""
        SELECT 
            c.id,
            c.name,
            c.alias,
            c.status::text as status,
            c.type::text as type,
            c.redirect_mode::text as redirect_mode,
            c.domain_id,
            c.traffic_source_id,
            c.config,
            c.notes,
            c.group_id,
            c.created_at,
            c.updated_at,
            COALESCE(SUM(s.clicks), 0)::bigint as clicks,
            COALESCE(SUM(s.unique_clicks), 0)::bigint as unique_clicks,
            COALESCE(SUM(s.conversions), 0)::bigint as conversions,
            COALESCE(SUM(s.revenue), 0)::real as revenue,
            COALESCE(SUM(s.cost), 0)::real as cost,
            (COALESCE(SUM(s.revenue), 0) - COALESCE(SUM(s.cost), 0))::real as profit
        FROM campaigns c
        LEFT JOIN clicks_daily_stats s ON s.campaign_id = c.id
            AND s.date >= :date_from AND s.date <= :date_to
        WHERE {where_sql}
        GROUP BY c.id, c.name, c.alias, c.status, c.type, c.redirect_mode, 
                 c.domain_id, c.traffic_source_id, c.config, c.notes, c.group_id,
                 c.created_at, c.updated_at
        ORDER BY c.id ASC
    """)

    result = db.execute(query, params)
    rows = result.fetchall()

    campaigns = []
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

        campaigns.append({
            "id": row.id,
            "name": row.name,
            "alias": row.alias,
            "status": row.status,
            "type": row.type,
            "redirect_mode": row.redirect_mode,
            "domain_id": row.domain_id,
            "traffic_source_id": row.traffic_source_id,
            "config": row.config,
            "notes": row.notes,
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

    return campaigns

@router.post("/", response_model=dict)
def create_campaign(data: CampaignIn, db: Session = Depends(get_db)):
    campaign = CampaignORM(**data.dict())
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return {"message": "Campaign created", "id": campaign.id}

@router.put("/{campaign_id}", response_model=CampaignOut)
def update_campaign(campaign_id: int, data: CampaignIn, db: Session = Depends(get_db)):
    campaign = db.query(CampaignORM).filter(CampaignORM.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    for key, value in data.dict().items():
        setattr(campaign, key, value)
    campaign.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(campaign)
    return campaign

@router.delete("/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(CampaignORM).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(404, detail="Campaign not found")

    db.delete(campaign)
    db.commit()
    return {"message": "Campaign deleted"}
