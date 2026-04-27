from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from datetime import datetime, timedelta

from db import get_db
from models import Campaign

router = APIRouter()


@router.get("/campaigns")
def list_campaigns(
    db: Session = Depends(get_db),
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD")
):
    """
    Get list of campaigns with statistics.
    If date_from/date_to not provided, uses last 30 days.
    """
    # Default date range: last 30 days
    if not date_to:
        date_to = datetime.utcnow().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    # SQL query to get campaigns with aggregated statistics
    query = text("""
        SELECT 
            c.id,
            c.name,
            c.alias,
            c.status,
            c.type,
            c.domain_id,
            c.traffic_source_id,
            c.created_at,
            COALESCE(SUM(s.clicks), 0)::bigint as clicks,
            COALESCE(SUM(s.unique_clicks), 0)::bigint as unique_clicks,
            COALESCE(SUM(s.conversions), 0)::bigint as conversions,
            COALESCE(SUM(s.revenue), 0)::real as revenue,
            COALESCE(SUM(s.cost), 0)::real as cost,
            (COALESCE(SUM(s.revenue), 0) - COALESCE(SUM(s.cost), 0))::real as profit
        FROM campaigns c
        LEFT JOIN clicks_daily_stats s ON s.campaign_id = c.id
            AND s.date >= :date_from AND s.date <= :date_to
        WHERE c.status IN ('active', 'paused')
        GROUP BY c.id, c.name, c.alias, c.status, c.type, c.domain_id, c.traffic_source_id, c.created_at
        ORDER BY c.id DESC
    """)

    result = db.execute(query, {"date_from": date_from, "date_to": date_to})
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
            "domain_id": row.domain_id,
            "traffic_source_id": row.traffic_source_id,
            "created_at": row.created_at,
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


@router.get("/campaign/{campaign_id}")
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    """Get single campaign with statistics."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Default date range: last 30 days
    if not date_to:
        date_to = datetime.utcnow().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    # Get statistics for this campaign
    stats_query = text("""
        SELECT 
            COALESCE(SUM(clicks), 0)::bigint as clicks,
            COALESCE(SUM(unique_clicks), 0)::bigint as unique_clicks,
            COALESCE(SUM(conversions), 0)::bigint as conversions,
            COALESCE(SUM(revenue), 0)::real as revenue,
            COALESCE(SUM(cost), 0)::real as cost,
            (COALESCE(SUM(revenue), 0) - COALESCE(SUM(cost), 0))::real as profit
        FROM clicks_daily_stats
        WHERE campaign_id = :campaign_id
            AND date >= :date_from AND date <= :date_to
    """)

    result = db.execute(stats_query, {
        "campaign_id": campaign_id,
        "date_from": date_from,
        "date_to": date_to
    })
    stats = result.fetchone()

    clicks = stats.clicks or 0
    conversions = stats.conversions or 0
    revenue = stats.revenue or 0
    cost = stats.cost or 0
    profit = stats.profit or 0

    roi = (profit / cost * 100) if cost > 0 else 0
    cr = (conversions / clicks * 100) if clicks > 0 else 0

    return {
        "id": campaign.id,
        "name": campaign.name,
        "alias": campaign.alias,
        "status": campaign.status.value if campaign.status else None,
        "type": campaign.type.value if campaign.type else None,
        "domain_id": campaign.domain_id,
        "traffic_source_id": campaign.traffic_source_id,
        "config": campaign.config,
        "notes": campaign.notes,
        "created_at": campaign.created_at,
        "updated_at": campaign.updated_at,
        "clicks": clicks,
        "unique_clicks": stats.unique_clicks or 0,
        "conversions": conversions,
        "revenue": round(revenue, 2),
        "cost": round(cost, 2),
        "profit": round(profit, 2),
        "roi": round(roi, 2),
        "cr": round(cr, 2)
    }


@router.get("/campaigns/stats")
def get_campaigns_stats_summary(
    db: Session = Depends(get_db),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    """Get aggregated statistics for all campaigns."""
    if not date_to:
        date_to = datetime.utcnow().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    query = text("""
        SELECT 
            COUNT(DISTINCT campaign_id) as campaigns_count,
            COALESCE(SUM(clicks), 0)::bigint as total_clicks,
            COALESCE(SUM(unique_clicks), 0)::bigint as total_unique_clicks,
            COALESCE(SUM(conversions), 0)::bigint as total_conversions,
            COALESCE(SUM(revenue), 0)::real as total_revenue,
            COALESCE(SUM(cost), 0)::real as total_cost,
            (COALESCE(SUM(revenue), 0) - COALESCE(SUM(cost), 0))::real as total_profit
        FROM clicks_daily_stats
        WHERE date >= :date_from AND date <= :date_to
    """)

    result = db.execute(query, {"date_from": date_from, "date_to": date_to})
    stats = result.fetchone()

    total_clicks = stats.total_clicks or 0
    total_conversions = stats.total_conversions or 0
    total_revenue = stats.total_revenue or 0
    total_cost = stats.total_cost or 0
    total_profit = stats.total_profit or 0

    roi = (total_profit / total_cost * 100) if total_cost > 0 else 0
    cr = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0

    return {
        "date_from": date_from,
        "date_to": date_to,
        "campaigns_count": stats.campaigns_count or 0,
        "total_clicks": total_clicks,
        "total_unique_clicks": stats.total_unique_clicks or 0,
        "total_conversions": total_conversions,
        "total_revenue": round(total_revenue, 2),
        "total_cost": round(total_cost, 2),
        "total_profit": round(total_profit, 2),
        "roi": round(roi, 2),
        "cr": round(cr, 2)
    }
