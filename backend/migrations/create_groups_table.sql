-- ============================================
-- Migration: Create groups table
-- Date: 2026-04-28
-- Description: Groups for organizing campaigns, offers, and sources
-- ============================================

-- Create groups table
CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    type VARCHAR(50) NOT NULL DEFAULT 'campaign', -- 'campaign', 'offer', 'source'
    color VARCHAR(7) DEFAULT '#6366f1',           -- Hex color for UI
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for groups table
CREATE INDEX IF NOT EXISTS idx_groups_type ON groups(type);
CREATE INDEX IF NOT EXISTS idx_groups_name ON groups(name);

-- Add group_id column to campaigns
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS group_id INTEGER REFERENCES groups(id);
CREATE INDEX IF NOT EXISTS idx_campaigns_group_id ON campaigns(group_id);

-- Add group_id column to offers
ALTER TABLE offers ADD COLUMN IF NOT EXISTS group_id INTEGER REFERENCES groups(id);
CREATE INDEX IF NOT EXISTS idx_offers_group_id ON offers(group_id);

-- Add group_id column to sources
ALTER TABLE sources ADD COLUMN IF NOT EXISTS group_id INTEGER REFERENCES groups(id);
CREATE INDEX IF NOT EXISTS idx_sources_group_id ON sources(group_id);

-- ============================================
-- Verification queries (run manually to check)
-- ============================================
-- SELECT * FROM groups;
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'groups';
-- \d campaigns | grep group_id
-- \d offers | grep group_id
-- \d sources | grep group_id
