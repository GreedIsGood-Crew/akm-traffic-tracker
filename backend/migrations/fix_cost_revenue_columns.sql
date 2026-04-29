-- ============================================
-- Migration: Fix cost/revenue/profit calculations
-- Date: 2024-01-XX
-- Description: Fix clicks_daily_stats VIEW to use correct Keitaro logic
--
-- KEITARO LOGIC:
-- - Cost (Расход) = money spent on traffic (CPC from traffic source)
-- - Revenue (Доход) = payout from affiliate network (what we earn)
-- - Profit = Revenue - Cost
--
-- CURRENT ISSUE:
-- - VIEW uses payout as cost, which is WRONG
-- - payout = money from affiliate = THIS IS REVENUE!
-- ============================================

-- Step 1: Add cost column to conversions_data if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'conversions_data' AND column_name = 'cost'
    ) THEN
        ALTER TABLE conversions_data ADD COLUMN cost REAL DEFAULT 0;
        COMMENT ON COLUMN conversions_data.cost IS 'Money spent on traffic (from traffic source CPC/cost parameter)';
    END IF;
END $$;

-- Step 2: Drop and recreate the VIEW with correct logic
DROP VIEW IF EXISTS clicks_daily_stats CASCADE;

-- Create view for daily stats with CORRECT Keitaro logic
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
    
    -- Conversions: sale + lead (Keitaro includes both in CR calculation)
    -- But for confirmed conversions, typically only sale/upsale
    count(*) FILTER (WHERE status IN ('sale', 'upsale', 'lead')) AS conversions,
    
    -- Leads: pending/unconfirmed (lead status from postback)
    count(*) FILTER (WHERE status = 'lead') AS leads,
    
    -- Sales: confirmed sales only
    count(*) FILTER (WHERE status IN ('sale', 'upsale')) AS sales,
    
    -- Cost = money spent on traffic (from traffic source)
    COALESCE(sum(cost), 0::real) AS cost,
    
    -- Revenue = payout from affiliate network (what we earn!)
    -- This is the CORRECT mapping: payout from affiliate = our revenue
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

Keitaro Metrics:
- Clicks = all visits registered
- Conversions = sale + upsale + lead (all conversion events)
- Sales = only sale/upsale (confirmed)
- Leads = only lead (pending confirmation)
- Cost = money spent on traffic (passed via cost parameter)
- Revenue = payout from affiliate network (what we earn for conversions)
- Profit = Revenue - Cost

CR (Conversion Rate) = conversions / clicks × 100
ROI = (Revenue - Cost) / Cost × 100 = Profit / Cost × 100';
