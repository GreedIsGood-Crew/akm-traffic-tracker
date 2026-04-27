from fastapi import APIRouter, Request, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from db import get_db
from clickHouse import get_recent_visits, get_metrics_series
from schemas import Filters
from datetime import datetime, timedelta
from typing import Optional

router = APIRouter()


@router.post("/visits")
async def get_visits(
        request: Request,
        filters: Filters
):
    try:
        ch = request.app.state.ch
        rows = get_recent_visits(ch, filters)
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metrics")
async def get_metrics(request: Request, filters: Filters):
    ch = request.app.state.ch
    series = get_metrics_series(ch, filters)

    total_visits = sum(row['visits'] for row in series)
    total_unique_visits = sum(row['unique_visits'] for row in series)
    total_clicks = sum(row['clicks'] for row in series)
    total_unique_clicks = sum(row['unique_clicks'] for row in series)
    total_conversions = sum(row['conversions'] for row in series)
    total_cost = sum(row['cost'] or 0 for row in series)
    total_revenue = sum(row['revenue'] or 0 for row in series)
    roi = f"{round(((total_revenue - total_cost) / total_cost * 100), 2)}%" if total_cost else "—"

    return {
        "metrics": {
            "visits": total_visits,
            "unique_visits": total_unique_visits,
            "clicks": total_clicks,
            "unique_clicks": total_unique_clicks,
            "conversions": total_conversions,
            "cost": round(total_cost, 2),
            "revenue": round(total_revenue, 2),
            "roi": roi
        },
        "chart": {
            "labels": [str(row["day"]) for row in series],
            "visits": [row["visits"] for row in series],
            "unique_visits": [row["unique_visits"] for row in series],
            "clicks": [row["clicks"] for row in series],
            "conversions": [row["conversions"] for row in series],
            "unique_clicks": [row["unique_clicks"] for row in series]
        }
    }


@router.get("/top-campaigns")
def get_top_campaigns(
    db: Session = Depends(get_db),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(10)
):
    """Get top campaigns by revenue."""
    if not date_to:
        date_to = datetime.utcnow().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    query = text("""
        SELECT 
            c.id,
            c.name,
            c.alias,
            COALESCE(SUM(s.clicks), 0)::bigint as clicks,
            COALESCE(SUM(s.conversions), 0)::bigint as conversions,
            COALESCE(SUM(s.revenue), 0)::real as revenue,
            COALESCE(SUM(s.cost), 0)::real as cost,
            (COALESCE(SUM(s.revenue), 0) - COALESCE(SUM(s.cost), 0))::real as profit
        FROM campaigns c
        LEFT JOIN clicks_daily_stats s ON s.campaign_id = c.id
            AND s.date >= :date_from AND s.date <= :date_to
        GROUP BY c.id, c.name, c.alias
        ORDER BY revenue DESC
        LIMIT :limit
    """)

    result = db.execute(query, {"date_from": date_from, "date_to": date_to, "limit": limit})
    rows = result.fetchall()

    return [
        {
            "id": row.id,
            "name": row.name,
            "alias": row.alias,
            "clicks": row.clicks or 0,
            "conversions": row.conversions or 0,
            "revenue": round(row.revenue or 0, 2),
            "cost": round(row.cost or 0, 2),
            "profit": round(row.profit or 0, 2)
        }
        for row in rows
    ]


@router.get("/top-offers")
def get_top_offers(
    db: Session = Depends(get_db),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(10)
):
    """Get top offers by revenue."""
    if not date_to:
        date_to = datetime.utcnow().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    query = text("""
        SELECT 
            o.id,
            o.name,
            COALESCE(SUM(s.clicks), 0)::bigint as clicks,
            COALESCE(SUM(s.conversions), 0)::bigint as conversions,
            COALESCE(SUM(s.revenue), 0)::real as revenue,
            COALESCE(SUM(s.cost), 0)::real as cost,
            (COALESCE(SUM(s.revenue), 0) - COALESCE(SUM(s.cost), 0))::real as profit
        FROM offers o
        LEFT JOIN clicks_daily_stats s ON s.offer_id = o.id
            AND s.date >= :date_from AND s.date <= :date_to
        GROUP BY o.id, o.name
        ORDER BY revenue DESC
        LIMIT :limit
    """)

    result = db.execute(query, {"date_from": date_from, "date_to": date_to, "limit": limit})
    rows = result.fetchall()

    return [
        {
            "id": row.id,
            "name": row.name,
            "clicks": row.clicks or 0,
            "conversions": row.conversions or 0,
            "revenue": round(row.revenue or 0, 2),
            "cost": round(row.cost or 0, 2),
            "profit": round(row.profit or 0, 2)
        }
        for row in rows
    ]


@router.get("/stats-by-country")
def get_stats_by_country(
    db: Session = Depends(get_db),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(10)
):
    """Get statistics grouped by country."""
    if not date_to:
        date_to = datetime.utcnow().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    query = text("""
        SELECT 
            COALESCE(country, 'Unknown') as country,
            SUM(clicks)::bigint as clicks,
            SUM(conversions)::bigint as conversions,
            SUM(revenue)::real as revenue
        FROM clicks_daily_stats
        WHERE date >= :date_from AND date <= :date_to
        GROUP BY country
        ORDER BY clicks DESC
        LIMIT :limit
    """)

    result = db.execute(query, {"date_from": date_from, "date_to": date_to, "limit": limit})
    rows = result.fetchall()

    return [
        {
            "country": row.country or "Unknown",
            "clicks": row.clicks or 0,
            "conversions": row.conversions or 0,
            "revenue": round(row.revenue or 0, 2)
        }
        for row in rows
    ]


@router.get("/stats-summary")
def get_stats_summary(
    db: Session = Depends(get_db),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    """Get overall statistics summary."""
    if not date_to:
        date_to = datetime.utcnow().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    query = text("""
        SELECT 
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
    row = result.fetchone()

    total_clicks = row.total_clicks or 0
    total_conversions = row.total_conversions or 0
    total_revenue = row.total_revenue or 0
    total_cost = row.total_cost or 0
    total_profit = row.total_profit or 0

    roi = (total_profit / total_cost * 100) if total_cost > 0 else 0
    cr = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0

    return {
        "clicks": total_clicks,
        "unique_clicks": row.total_unique_clicks or 0,
        "conversions": total_conversions,
        "revenue": round(total_revenue, 2),
        "cost": round(total_cost, 2),
        "profit": round(total_profit, 2),
        "roi": round(roi, 2),
        "cr": round(cr, 2)
    }


@router.get("/chart-data")
def get_chart_data(
    db: Session = Depends(get_db),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    """Get daily chart data."""
    if not date_to:
        date_to = datetime.utcnow().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    query = text("""
        SELECT 
            date,
            SUM(clicks)::bigint as clicks,
            SUM(unique_clicks)::bigint as unique_clicks,
            SUM(conversions)::bigint as conversions,
            SUM(revenue)::real as revenue,
            SUM(cost)::real as cost
        FROM clicks_daily_stats
        WHERE date >= :date_from AND date <= :date_to
        GROUP BY date
        ORDER BY date ASC
    """)

    result = db.execute(query, {"date_from": date_from, "date_to": date_to})
    rows = result.fetchall()

    return {
        "labels": [str(row.date) for row in rows],
        "clicks": [row.clicks or 0 for row in rows],
        "unique_clicks": [row.unique_clicks or 0 for row in rows],
        "conversions": [row.conversions or 0 for row in rows],
        "revenue": [round(row.revenue or 0, 2) for row in rows],
        "cost": [round(row.cost or 0, 2) for row in rows]
    }
