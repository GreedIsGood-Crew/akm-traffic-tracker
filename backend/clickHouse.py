"""
PostgreSQL stub for ClickHouse functions (Postgres-only mode).
All data lives in conversions_data (VIEW over tracker_clicks + tracker_conversions).
"""
import os
from datetime import datetime, timedelta, date
from typing import List, Optional, Any, Tuple, Dict, Union

import psycopg2
import psycopg2.extras

from schemas import Filters


def _get_pg_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'tracker-postgres'),
        port=int(os.environ.get('DB_PORT', '5432')),
        dbname=os.environ.get('DB_NAME', 'tracker'),
        user=os.environ.get('DB_USER', 'tracker'),
        password=os.environ.get('DB_PASSWORD', 'tracker_local_dev'),
    )


def get_clickhouse_client():
    """Returns a PG connection (duck-typed as client for compat)."""
    return _get_pg_conn()


def build_filters(filters):
    def get(val, default=None):
        if isinstance(filters, dict):
            return filters.get(val, default)
        return getattr(filters, val, default)

    conditions = []
    params = {}

    date_from = get("date_from")
    date_to = get("date_to")
    if date_from and date_to:
        conditions.append("received_at::date BETWEEN %(date_from)s::date AND %(date_to)s::date")
        params["date_from"] = date_from
        params["date_to"] = date_to

    campaigns = get("campaigns")
    if campaigns:
        conditions.append("campaign_id = ANY(%(campaigns)s)")
        params["campaigns"] = list(campaigns)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_clause, params


def get_recent_visits(client, filters, limit=100):
    where_clause, params = build_filters(filters)
    params['limit'] = limit

    query = f"""
        SELECT ip::text, country, '' as url, '' as referrer, received_at
        FROM conversions_data
        {where_clause}
        ORDER BY received_at DESC
        LIMIT %(limit)s
    """

    conn = _get_pg_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def generate_date_range(start, end):
    date_from = datetime.strptime(start, "%Y-%m-%d")
    date_to = datetime.strptime(end, "%Y-%m-%d")
    return [(date_from + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range((date_to - date_from).days + 1)]


def get_metrics_series(client, filters, limit=30):
    filters_dict = filters.dict() if hasattr(filters, 'dict') else dict(filters)

    if not filters_dict.get("date_from") or not filters_dict.get("date_to"):
        end_date = date.today()
        start_date = end_date - timedelta(days=limit - 1)
        filters_dict["date_from"] = str(start_date)
        filters_dict["date_to"] = str(end_date)
    else:
        start_date = date.fromisoformat(filters_dict["date_from"])
        end_date = date.fromisoformat(filters_dict["date_to"])

    where_clause, params = build_filters(filters_dict)

    query = f"""
        SELECT
            received_at::date AS day,
            count(*) AS visits,
            count(DISTINCT CASE WHEN status IS NULL THEN visitor_id END) AS unique_visits,
            count(*) FILTER (WHERE status IS NOT NULL) AS clicks,
            count(DISTINCT CASE WHEN status IS NOT NULL THEN visitor_id END) AS unique_clicks,
            count(*) FILTER (WHERE status IN ('sale', 'upsale')) AS conversions,
            COALESCE(sum(payout), 0)::float AS cost,
            COALESCE(sum(revenue), 0)::float AS revenue
        FROM conversions_data
        {where_clause}
        GROUP BY day
        ORDER BY day
    """

    conn = _get_pg_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            raw_rows = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    data_by_day = {row["day"]: row for row in raw_rows}

    output = []
    current = start_date
    while current <= end_date:
        row = data_by_day.get(current, {
            "day": current,
            "visits": 0,
            "unique_visits": 0,
            "clicks": 0,
            "unique_clicks": 0,
            "conversions": 0,
            "cost": 0.0,
            "revenue": 0.0
        })
        output.append(row)
        current += timedelta(days=1)

    return output
