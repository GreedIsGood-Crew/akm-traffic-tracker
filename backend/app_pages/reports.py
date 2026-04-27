from fastapi import APIRouter, Request, Depends, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from typing import List, Optional
from db import get_db
from models.base import Base
import csv
import io

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime

router = APIRouter()

class Conversion(Base):
    __tablename__ = "conversions_data"

    id = Column(Integer, primary_key=True, index=True)
    received_at = Column(DateTime)
    click_id = Column(String)
    campaign_id = Column(Integer)
    offer_id = Column(Integer)
    landing_id = Column(Integer)
    status = Column(String)
    external_id = Column(String)
    payout = Column(Float)
    revenue = Column(Float)
    profit = Column(Float)
    currency = Column(String)
    transaction_id = Column(String)
    country = Column(String)
    region = Column(String)
    city = Column(String)
    ip = Column(String)
    visitor_id = Column(String)
    sub_id_1 = Column(String)
    sub_id_2 = Column(String)
    sub_id_3 = Column(String)
    sub_id_4 = Column(String)
    sub_id_5 = Column(String)
    sub_id_6 = Column(String)
    sub_id_7 = Column(String)
    sub_id_8 = Column(String)
    sub_id_9 = Column(String)
    sub_id_10 = Column(String)
    utm_campaign = Column(String)
    utm_creative = Column(String)
    utm_source = Column(String)
    traffic_source_name = Column(String)
    os = Column(String)
    isp = Column(String)
    is_using_proxy = Column(Boolean)
    is_bot = Column(Boolean)
    device_type = Column(String)

@router.get("/")
def get_conversions(request: Request, limit: int = 100, db: Session = Depends(get_db)):

    # разрешённые поля фильтрации
    ALLOWED_FILTER_FIELDS = {
        "campaign_id", "offer_id", "landing_id", "status", "click_id", "external_id",
        "sub_id_1", "sub_id_2", "sub_id_3", "sub_id_4", "sub_id_5",
        "sub_id_6", "sub_id_7", "sub_id_8", "sub_id_9", "sub_id_10",
        "utm_source", "utm_campaign", "utm_creative", "traffic_source_name"
    }

    query = db.query(Conversion)

    # Применяем фильтры
    for key, value in request.query_params.items():
        if key in ALLOWED_FILTER_FIELDS:
            column = getattr(Conversion, key, None)
            if column is not None:
                query = query.filter(column == value)
        elif key == "date_from":
            query = query.filter(Conversion.received_at >= datetime.fromisoformat(value))
        elif key == "date_to":
            query = query.filter(Conversion.received_at <= datetime.fromisoformat(value))

    rows = query.order_by(Conversion.received_at.desc()).limit(limit).all()

    # Преобразуем ORM-объекты в dict
    return [row.__dict__ for row in rows]


# Group by mapping
GROUP_BY_MAPPING = {
    "campaign": ("c.name", "campaigns c", "s.campaign_id = c.id", "campaign_name"),
    "offer": ("o.name", "offers o", "s.offer_id = o.id", "offer_name"),
    "source": ("src.name", "sources src JOIN campaigns camp ON camp.traffic_source_id = src.id", "s.campaign_id = camp.id", "source_name"),
    "country": ("s.country", None, None, "country"),
    "date": ("s.date", None, None, "date"),
}


@router.get("/aggregated")
def get_aggregated_report(
    db: Session = Depends(get_db),
    group_by: str = Query("campaign", description="Group by: campaign, offer, source, country, date"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    """Get aggregated report with grouping support."""
    if not date_to:
        date_to = datetime.utcnow().strftime("%Y-%m-%d")
    if not date_from:
        date_from = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    # Build query based on group_by
    if group_by == "campaign":
        query = text("""
            SELECT 
                c.id as entity_id,
                c.name as entity_name,
                COALESCE(SUM(s.clicks), 0)::bigint as clicks,
                COALESCE(SUM(s.unique_clicks), 0)::bigint as unique_clicks,
                COALESCE(SUM(s.conversions), 0)::bigint as conversions,
                COALESCE(SUM(s.revenue), 0)::real as revenue,
                COALESCE(SUM(s.cost), 0)::real as cost,
                (COALESCE(SUM(s.revenue), 0) - COALESCE(SUM(s.cost), 0))::real as profit
            FROM clicks_daily_stats s
            JOIN campaigns c ON s.campaign_id = c.id
            WHERE s.date >= :date_from AND s.date <= :date_to
            GROUP BY c.id, c.name
            ORDER BY revenue DESC
        """)
    elif group_by == "offer":
        query = text("""
            SELECT 
                o.id as entity_id,
                o.name as entity_name,
                COALESCE(SUM(s.clicks), 0)::bigint as clicks,
                COALESCE(SUM(s.unique_clicks), 0)::bigint as unique_clicks,
                COALESCE(SUM(s.conversions), 0)::bigint as conversions,
                COALESCE(SUM(s.revenue), 0)::real as revenue,
                COALESCE(SUM(s.cost), 0)::real as cost,
                (COALESCE(SUM(s.revenue), 0) - COALESCE(SUM(s.cost), 0))::real as profit
            FROM clicks_daily_stats s
            JOIN offers o ON s.offer_id = o.id
            WHERE s.date >= :date_from AND s.date <= :date_to
            GROUP BY o.id, o.name
            ORDER BY revenue DESC
        """)
    elif group_by == "source":
        query = text("""
            SELECT 
                src.id as entity_id,
                src.name as entity_name,
                COALESCE(SUM(s.clicks), 0)::bigint as clicks,
                COALESCE(SUM(s.unique_clicks), 0)::bigint as unique_clicks,
                COALESCE(SUM(s.conversions), 0)::bigint as conversions,
                COALESCE(SUM(s.revenue), 0)::real as revenue,
                COALESCE(SUM(s.cost), 0)::real as cost,
                (COALESCE(SUM(s.revenue), 0) - COALESCE(SUM(s.cost), 0))::real as profit
            FROM clicks_daily_stats s
            JOIN campaigns c ON s.campaign_id = c.id
            JOIN sources src ON c.traffic_source_id = src.id
            WHERE s.date >= :date_from AND s.date <= :date_to
            GROUP BY src.id, src.name
            ORDER BY revenue DESC
        """)
    elif group_by == "country":
        query = text("""
            SELECT 
                0 as entity_id,
                COALESCE(s.country, 'Unknown') as entity_name,
                COALESCE(SUM(s.clicks), 0)::bigint as clicks,
                COALESCE(SUM(s.unique_clicks), 0)::bigint as unique_clicks,
                COALESCE(SUM(s.conversions), 0)::bigint as conversions,
                COALESCE(SUM(s.revenue), 0)::real as revenue,
                COALESCE(SUM(s.cost), 0)::real as cost,
                (COALESCE(SUM(s.revenue), 0) - COALESCE(SUM(s.cost), 0))::real as profit
            FROM clicks_daily_stats s
            WHERE s.date >= :date_from AND s.date <= :date_to
            GROUP BY s.country
            ORDER BY clicks DESC
        """)
    elif group_by == "date":
        query = text("""
            SELECT 
                0 as entity_id,
                s.date::text as entity_name,
                COALESCE(SUM(s.clicks), 0)::bigint as clicks,
                COALESCE(SUM(s.unique_clicks), 0)::bigint as unique_clicks,
                COALESCE(SUM(s.conversions), 0)::bigint as conversions,
                COALESCE(SUM(s.revenue), 0)::real as revenue,
                COALESCE(SUM(s.cost), 0)::real as cost,
                (COALESCE(SUM(s.revenue), 0) - COALESCE(SUM(s.cost), 0))::real as profit
            FROM clicks_daily_stats s
            WHERE s.date >= :date_from AND s.date <= :date_to
            GROUP BY s.date
            ORDER BY s.date DESC
        """)
    else:
        # Default to campaign
        query = text("""
            SELECT 
                c.id as entity_id,
                c.name as entity_name,
                COALESCE(SUM(s.clicks), 0)::bigint as clicks,
                COALESCE(SUM(s.unique_clicks), 0)::bigint as unique_clicks,
                COALESCE(SUM(s.conversions), 0)::bigint as conversions,
                COALESCE(SUM(s.revenue), 0)::real as revenue,
                COALESCE(SUM(s.cost), 0)::real as cost,
                (COALESCE(SUM(s.revenue), 0) - COALESCE(SUM(s.cost), 0))::real as profit
            FROM clicks_daily_stats s
            JOIN campaigns c ON s.campaign_id = c.id
            WHERE s.date >= :date_from AND s.date <= :date_to
            GROUP BY c.id, c.name
            ORDER BY revenue DESC
        """)

    result = db.execute(query, {"date_from": date_from, "date_to": date_to})
    rows = result.fetchall()

    report = []
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

        report.append({
            "id": row.entity_id,
            "name": row.entity_name or "Unknown",
            "clicks": clicks,
            "unique_clicks": row.unique_clicks or 0,
            "conversions": conversions,
            "revenue": round(revenue, 2),
            "cost": round(cost, 2),
            "profit": round(profit, 2),
            "roi": round(roi, 2),
            "cr": round(cr, 2)
        })

    return report


@router.get("/export-csv")
def export_csv(
    db: Session = Depends(get_db),
    group_by: str = Query("campaign"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    """Export aggregated report as CSV."""
    # Get aggregated data
    data = get_aggregated_report(db, group_by, date_from, date_to)

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(["Name", "Clicks", "Unique Clicks", "Conversions", "Revenue", "Cost", "Profit", "ROI %", "CR %"])

    # Data rows
    for row in data:
        writer.writerow([
            row["name"],
            row["clicks"],
            row["unique_clicks"],
            row["conversions"],
            row["revenue"],
            row["cost"],
            row["profit"],
            row["roi"],
            row["cr"]
        ])

    csv_content = output.getvalue()
    output.close()

    filename = f"report_{group_by}_{date_from or 'all'}_{date_to or 'all'}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/summary")
def get_report_summary(
    db: Session = Depends(get_db),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    """Get overall summary for the report period."""
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
        "cr": round(cr, 2),
        "date_from": date_from,
        "date_to": date_to
    }
