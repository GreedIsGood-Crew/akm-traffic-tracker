-- ============================================
-- Migration: Create/update clicks_daily_stats VIEW
-- Date: 2024-XX-XX (Updated)
-- Description: Aggregated daily statistics for clicks and conversions
-- 
-- KEITARO LOGIC:
-- - Cost (Расход) = money spent on traffic (from traffic source CPC parameter)
-- - Revenue (Доход) = payout from affiliate network
-- - Profit = Revenue - Cost
-- - Conversions = sale + upsale + lead (all conversion events)
-- - CR = conversions / clicks × 100
-- - ROI = profit / cost × 100
--
-- This follows Keitaro logic where:
-- 1. Click is registered when user visits link (no status)
-- 2. Cost is passed from traffic source (CPC model)
-- 3. Conversion (lead/sale/etc) is registered via postback from affiliate network
-- 4. Revenue = payout received from affiliate for conversion
-- ============================================

-- First ensure cost column exists in conversions_data
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'conversions_data' AND column_name = 'cost'
    ) THEN
        ALTER TABLE conversions_data ADD COLUMN cost REAL DEFAULT 0;
    END IF;
END $$;

-- Drop existing view if exists
DROP VIEW IF EXISTS clicks_daily_stats CASCADE;

-- Create view for daily stats
CREATE VIEW clicks_daily_stats AS
SELECT 
    row_number() OVER ()::integer AS id,
    received_at::date AS date,
    campaign_id,
    offer_id,
    landing_id,
    NULL::integer AS traffic_source_id,
    country,
    
    -- Clicks: total records (all visits)
    count(*) AS clicks,
    
    -- Unique clicks: distinct visitor_id
    count(DISTINCT visitor_id) AS unique_clicks,
    
    -- Conversions: sale + upsale + lead (all conversion events for CR)
    count(*) FILTER (WHERE status IN ('sale', 'upsale', 'lead')) AS conversions,
    
    -- Leads: pending/unconfirmed (lead status from postback)
    count(*) FILTER (WHERE status = 'lead') AS leads,
    
    -- Sales: confirmed only (sale/upsale)
    count(*) FILTER (WHERE status IN ('sale', 'upsale')) AS sales,
    
    -- Cost = money spent on traffic (from traffic source CPC/cost parameter)
    COALESCE(sum(cost), 0::real) AS cost,
    
    -- Revenue = payout from affiliate network (THIS IS OUR INCOME!)
    COALESCE(sum(payout), 0::real) AS revenue,
    
    -- Profit = Revenue - Cost
    COALESCE(sum(payout), 0::real) - COALESCE(sum(cost), 0::real) AS profit,
    
    min(received_at)::timestamp with time zone AS created_at,
    max(received_at)::timestamp with time zone AS updated_at
    
FROM conversions_data
GROUP BY 
    received_at::date,
    campaign_id,
    offer_id,
    landing_id,
    country;

-- Comment
COMMENT ON VIEW clicks_daily_stats IS 
'Aggregated daily click and conversion statistics (Keitaro-style).
- Clicks = all records in conversions_data (visits)
- Conversions = sale + upsale + lead (for CR calculation)
- Sales = only sale/upsale (confirmed)
- Leads = lead status (pending confirmation)
- Cost = money spent on traffic (from traffic source)
- Revenue = payout from affiliate network
- Profit = Revenue - Cost';
