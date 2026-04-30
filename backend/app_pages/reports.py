from fastapi import APIRouter, Request, Depends, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
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


# ====== Advanced Reports Models ======

class ReportFilter(BaseModel):
    field: str           # country, campaign_id, offer_id, status, etc.
    operator: str        # EQUALS, NOT_EQUALS, GREATER_THAN, LESS_THAN, CONTAINS, IN
    value: str           # Значение для сравнения

class AdvancedReportRequest(BaseModel):
    date_from: str
    date_to: str
    group_by: List[str]  # ['campaign', 'country'] — иерархическая группировка
    filters: Optional[List[ReportFilter]] = []
    metrics: Optional[List[str]] = ['clicks', 'conversions', 'revenue', 'cost', 'profit']


# ====== Advanced Reports Helpers ======

FIELD_MAPPING = {
    'campaign': 'c.name',
    'campaign_id': 's.campaign_id',
    'offer': 'o.name',
    'offer_id': 's.offer_id',
    'source': 'src.name',
    'country': 's.country',
    'date': 's.date',
    'status': 'cd.status',
    'clicks': 'clicks',
    'conversions': 'conversions',
    'revenue': 'revenue',
    'cost': 'cost',
    'profit': 'profit',
    'roi': 'roi'
}

OPERATOR_MAPPING = {
    'EQUALS': '=',
    'NOT_EQUALS': '!=',
    'GREATER_THAN': '>',
    'LESS_THAN': '<',
    'GREATER_OR_EQUAL': '>=',
    'LESS_OR_EQUAL': '<=',
    'CONTAINS': 'ILIKE',
    'IN': 'IN'
}


def build_filter_clause(filters: List[ReportFilter]) -> tuple:
    """Build WHERE clause from filters."""
    clauses = []
    params = {}
    
    for i, f in enumerate(filters):
        field = FIELD_MAPPING.get(f.field, f.field)
        op = OPERATOR_MAPPING.get(f.operator, '=')
        param_name = f"filter_{i}"
        
        if f.operator == 'CONTAINS':
            clauses.append(f"{field} ILIKE :{param_name}")
            params[param_name] = f"%{f.value}%"
        elif f.operator == 'IN':
            values = [v.strip() for v in f.value.split(',')]
            placeholders = ', '.join([f":{param_name}_{j}" for j in range(len(values))])
            clauses.append(f"{field} IN ({placeholders})")
            for j, v in enumerate(values):
                params[f"{param_name}_{j}"] = v
        else:
            clauses.append(f"{field} {op} :{param_name}")
            # Try to convert to number if numeric operator
            if f.operator in ('GREATER_THAN', 'LESS_THAN', 'GREATER_OR_EQUAL', 'LESS_OR_EQUAL'):
                try:
                    params[param_name] = float(f.value)
                except:
                    params[param_name] = f.value
            else:
                params[param_name] = f.value
    
    return ' AND '.join(clauses) if clauses else '1=1', params


# ====== Advanced Report Endpoint ======

@router.post("/advanced")
async def get_advanced_report(
    request: AdvancedReportRequest,
    db: Session = Depends(get_db)
):
    """
    Get advanced report with multiple groupings and filters.
    
    Group by hierarchy: First group is parent, subsequent are children.
    Example: group_by=['campaign', 'country'] → Campaign > Country
    """
    
    # Build filter clause
    filter_clause, filter_params = build_filter_clause(request.filters or [])
    
    # Build GROUP BY fields
    group_fields = []
    select_fields = []
    
    for g in request.group_by:
        if g == 'campaign':
            group_fields.append('s.campaign_id')
            group_fields.append('c.name')
            select_fields.append('s.campaign_id')
            select_fields.append('c.name as campaign_name')
        elif g == 'offer':
            group_fields.append('s.offer_id')
            group_fields.append('o.name')
            select_fields.append('s.offer_id')
            select_fields.append('o.name as offer_name')
        elif g == 'source':
            group_fields.append('c.traffic_source_id')
            group_fields.append('src.name')
            select_fields.append('c.traffic_source_id as source_id')
            select_fields.append('src.name as source_name')
        elif g == 'country':
            group_fields.append('s.country')
            select_fields.append("COALESCE(s.country, 'Unknown') as country")
        elif g == 'date':
            group_fields.append('s.date')
            select_fields.append('s.date::text as date')
    
    # Build metrics
    metrics_sql = []
    for m in request.metrics or ['clicks', 'conversions', 'revenue', 'cost', 'profit']:
        if m == 'clicks':
            metrics_sql.append('COALESCE(SUM(s.clicks), 0)::bigint as clicks')
        elif m == 'unique_clicks':
            metrics_sql.append('COALESCE(SUM(s.unique_clicks), 0)::bigint as unique_clicks')
        elif m == 'conversions':
            metrics_sql.append('COALESCE(SUM(s.conversions), 0)::bigint as conversions')
        elif m == 'revenue':
            metrics_sql.append('COALESCE(SUM(s.revenue), 0)::numeric(12,2) as revenue')
        elif m == 'cost':
            metrics_sql.append('COALESCE(SUM(s.cost), 0)::numeric(12,2) as cost')
        elif m == 'profit':
            metrics_sql.append('(COALESCE(SUM(s.revenue), 0) - COALESCE(SUM(s.cost), 0))::numeric(12,2) as profit')
        elif m == 'roi':
            metrics_sql.append('''
                CASE WHEN COALESCE(SUM(s.cost), 0) > 0 
                     THEN ROUND(((SUM(s.revenue) - SUM(s.cost)) / SUM(s.cost) * 100)::numeric, 2)
                     ELSE 0 
                END as roi
            ''')
        elif m == 'cr':
            metrics_sql.append('''
                CASE WHEN COALESCE(SUM(s.clicks), 0) > 0 
                     THEN ROUND((SUM(s.conversions)::numeric / SUM(s.clicks) * 100), 2)
                     ELSE 0 
                END as cr
            ''')
    
    # Build full query
    query = text(f"""
        SELECT 
            {', '.join(select_fields)},
            {', '.join(metrics_sql)}
        FROM clicks_daily_stats s
        LEFT JOIN campaigns c ON c.id = s.campaign_id
        LEFT JOIN offers o ON o.id = s.offer_id
        LEFT JOIN sources src ON src.id = c.traffic_source_id
        WHERE s.date BETWEEN :date_from AND :date_to
          AND ({filter_clause})
        GROUP BY {', '.join(group_fields)}
        ORDER BY {group_fields[0]} NULLS LAST
    """)
    
    params = {
        "date_from": request.date_from,
        "date_to": request.date_to,
        **filter_params
    }
    
    result = db.execute(query, params)
    rows = result.fetchall()
    
    # Convert to hierarchical structure if multiple groups
    if len(request.group_by) > 1:
        return build_hierarchy(rows, request.group_by)
    
    return [dict(row._mapping) for row in rows]


def build_hierarchy(rows, group_by: List[str]) -> List[dict]:
    """Build hierarchical data structure for multi-level grouping."""
    
    hierarchy = {}
    
    for row in rows:
        row_dict = dict(row._mapping)
        
        # Get parent key
        parent_key = row_dict.get(f"{group_by[0]}_id") or row_dict.get(group_by[0])
        parent_name = row_dict.get(f"{group_by[0]}_name", str(parent_key))
        
        if parent_key not in hierarchy:
            hierarchy[parent_key] = {
                "id": parent_key,
                "name": parent_name,
                "children": [],
                "totals": {k: 0 for k in ['clicks', 'conversions', 'revenue', 'cost', 'profit']}
            }
        
        # Add child data
        child = {k: v for k, v in row_dict.items() 
                 if not k.startswith(group_by[0])}
        hierarchy[parent_key]["children"].append(child)
        
        # Accumulate totals
        for metric in ['clicks', 'conversions', 'revenue', 'cost', 'profit']:
            if metric in row_dict:
                hierarchy[parent_key]["totals"][metric] += float(row_dict[metric] or 0)
    
    return list(hierarchy.values())


# ====== Click Log Endpoint ======

@router.get("/clicks-log")
async def get_clicks_log(
    click_id: Optional[str] = Query(None, description="Search by click_id"),
    campaign: Optional[str] = Query(None, description="Search by campaign name"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):
    """Get click log with search by click_id and campaign name."""
    
    where_clauses = []
    params = {"limit": limit, "offset": offset}
    
    if click_id:
        where_clauses.append("cd.click_id ILIKE :click_id")
        params["click_id"] = f"%{click_id}%"
    
    if campaign:
        where_clauses.append("c.name ILIKE :campaign")
        params["campaign"] = f"%{campaign}%"
    
    if date_from:
        where_clauses.append("cd.received_at >= :date_from::date")
        params["date_from"] = date_from
    
    if date_to:
        where_clauses.append("cd.received_at <= :date_to::date + INTERVAL '1 day'")
        params["date_to"] = date_to
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    query = text(f"""
        SELECT 
            cd.id,
            cd.click_id,
            cd.campaign_id,
            c.name as campaign_name,
            cd.offer_id,
            o.name as offer_name,
            cd.country,
            cd.ip,
            cd.status,
            cd.payout,
            cd.sub_id_1,
            cd.sub_id_2,
            cd.sub_id_3,
            cd.received_at::text as received_at
        FROM conversions_data cd
        LEFT JOIN campaigns c ON c.id = cd.campaign_id
        LEFT JOIN offers o ON o.id = cd.offer_id
        WHERE {where_sql}
        ORDER BY cd.received_at DESC
        LIMIT :limit OFFSET :offset
    """)
    
    result = db.execute(query, params)
    rows = result.fetchall()
    
    # Get total count
    count_query = text(f"""
        SELECT COUNT(*) 
        FROM conversions_data cd
        LEFT JOIN campaigns c ON c.id = cd.campaign_id
        WHERE {where_sql}
    """)
    count_params = {k: v for k, v in params.items() if k not in ('limit', 'offset')}
    total = db.execute(count_query, count_params).scalar()
    
    return {
        "items": [dict(row._mapping) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset
    }


# ====== Conversions Log Endpoint ======

@router.get("/conversions-log")
async def get_conversions_log(
    click_id: Optional[str] = Query(None, description="Search by click_id"),
    campaign: Optional[str] = Query(None, description="Search by campaign name"),
    status: Optional[str] = Query(None, description="Filter by status: lead, sale, upsale, rejected, hold, trash"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):
    """Get conversions log - only records where status IS NOT NULL."""
    
    where_clauses = ["cd.status IS NOT NULL"]  # Only conversions, not clicks
    params = {"limit": limit, "offset": offset}
    
    if click_id:
        where_clauses.append("cd.click_id ILIKE :click_id")
        params["click_id"] = f"%{click_id}%"
    
    if campaign:
        where_clauses.append("c.name ILIKE :campaign")
        params["campaign"] = f"%{campaign}%"
    
    if status:
        where_clauses.append("cd.status = :status::conversion_status")
        params["status"] = status
    
    if date_from:
        where_clauses.append("cd.received_at >= CAST(:date_from AS DATE)")
        params["date_from"] = date_from
    
    if date_to:
        where_clauses.append("cd.received_at <= CAST(:date_to AS DATE) + INTERVAL '1 day'")
        params["date_to"] = date_to
    
    where_sql = " AND ".join(where_clauses)
    
    query = text(f"""
        SELECT 
            cd.id,
            cd.click_id,
            cd.campaign_id,
            c.name as campaign_name,
            cd.offer_id,
            o.name as offer_name,
            cd.country,
            cd.ip,
            cd.status::text as status,
            cd.payout,
            cd.revenue,
            cd.transaction_id,
            cd.sub_id_1,
            cd.sub_id_2,
            cd.sub_id_3,
            cd.received_at::text as received_at
        FROM conversions_data cd
        LEFT JOIN campaigns c ON c.id = cd.campaign_id
        LEFT JOIN offers o ON o.id = cd.offer_id
        WHERE {where_sql}
        ORDER BY cd.received_at DESC
        LIMIT :limit OFFSET :offset
    """)
    
    result = db.execute(query, params)
    rows = result.fetchall()
    
    # Get total count
    count_query = text(f"""
        SELECT COUNT(*) 
        FROM conversions_data cd
        LEFT JOIN campaigns c ON c.id = cd.campaign_id
        WHERE {where_sql}
    """)
    count_params = {k: v for k, v in params.items() if k not in ('limit', 'offset')}
    total = db.execute(count_query, count_params).scalar()
    
    # Get stats by status
    stats_query = text("""
        SELECT 
            status::text as status,
            COUNT(*) as count,
            COALESCE(SUM(payout), 0) as total_payout
        FROM conversions_data
        WHERE status IS NOT NULL
        GROUP BY status
    """)
    stats_result = db.execute(stats_query)
    stats = {row.status: {"count": row.count, "payout": float(row.total_payout)} for row in stats_result.fetchall()}
    
    return {
        "items": [dict(row._mapping) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "stats": stats
    }


# ====== Clicks Log Full (all clicks) ======

@router.get("/clicks-log-full")
async def get_clicks_log_full(
    click_id: Optional[str] = Query(None, description="Search by click_id"),
    campaign: Optional[str] = Query(None, description="Search by campaign name"),
    country: Optional[str] = Query(None, description="Filter by country"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):
    """Get ALL clicks log (status can be NULL or any value)."""
    
    where_clauses = ["1=1"]
    params = {"limit": limit, "offset": offset}
    
    if click_id:
        where_clauses.append("cd.click_id ILIKE :click_id")
        params["click_id"] = f"%{click_id}%"
    
    if campaign:
        where_clauses.append("c.name ILIKE :campaign")
        params["campaign"] = f"%{campaign}%"
    
    if country:
        where_clauses.append("cd.country = :country")
        params["country"] = country
    
    if date_from:
        where_clauses.append("cd.received_at >= CAST(:date_from AS DATE)")
        params["date_from"] = date_from
    
    if date_to:
        where_clauses.append("cd.received_at <= CAST(:date_to AS DATE) + INTERVAL '1 day'")
        params["date_to"] = date_to
    
    where_sql = " AND ".join(where_clauses)
    
    query = text(f"""
        SELECT 
            cd.id,
            cd.click_id,
            cd.campaign_id,
            c.name as campaign_name,
            cd.offer_id,
            o.name as offer_name,
            cd.landing_id,
            cd.country,
            cd.region,
            cd.city,
            cd.ip::text as ip,
            cd.visitor_id,
            cd.os,
            cd.device_type,
            cd.is_bot,
            cd.is_using_proxy,
            cd.status::text as status,
            cd.payout,
            cd.sub_id_1,
            cd.sub_id_2,
            cd.sub_id_3,
            cd.sub_id_4,
            cd.sub_id_5,
            cd.utm_source,
            cd.utm_campaign,
            cd.utm_creative,
            cd.received_at::text as received_at
        FROM conversions_data cd
        LEFT JOIN campaigns c ON c.id = cd.campaign_id
        LEFT JOIN offers o ON o.id = cd.offer_id
        WHERE {where_sql}
        ORDER BY cd.received_at DESC
        LIMIT :limit OFFSET :offset
    """)
    
    result = db.execute(query, params)
    rows = result.fetchall()
    
    # Get total count
    count_query = text(f"""
        SELECT COUNT(*) 
        FROM conversions_data cd
        LEFT JOIN campaigns c ON c.id = cd.campaign_id
        WHERE {where_sql}
    """)
    count_params = {k: v for k, v in params.items() if k not in ('limit', 'offset')}
    total = db.execute(count_query, count_params).scalar()
    
    return {
        "items": [dict(row._mapping) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset
    }


# ====== Filter Options ======

@router.get("/filter-options")
async def get_filter_options(db: Session = Depends(get_db)):
    """Get filter options for dropdowns."""
    
    # Countries
    countries_query = text("""
        SELECT DISTINCT country FROM conversions_data 
        WHERE country IS NOT NULL 
        ORDER BY country
    """)
    countries = [row.country for row in db.execute(countries_query).fetchall()]
    
    # Campaigns
    campaigns_query = text("SELECT id, name FROM campaigns ORDER BY name")
    campaigns = [{"id": row.id, "name": row.name} for row in db.execute(campaigns_query).fetchall()]
    
    # Statuses
    statuses = ["lead", "sale", "upsale", "rejected", "hold", "trash"]
    
    return {
        "countries": countries,
        "campaigns": campaigns,
        "statuses": statuses
    }
