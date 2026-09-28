-- ====================================================================
-- FACEBOOK LEAD INTELLIGENCE V1 - DATABASE MIGRATION (PHASE 1)
-- Target Database: PostgreSQL 15+ / Supabase (crawl_data_fb)
-- Idempotent & Production Ready
-- ====================================================================

-- 0. EXTENSIONS & PREREQUISITES
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Clean up any empty temporary tables if existing
DROP TABLE IF EXISTS public.fb_comments CASCADE;
DROP TABLE IF EXISTS public.fb_leads CASCADE;
DROP TABLE IF EXISTS public.fb_posts CASCADE;
DROP TABLE IF EXISTS public.fb_pages CASCADE;

-- Auto-update updated_at trigger function
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ====================================================================
-- 1. SYSTEM FLAGS & CIRCUIT BREAKER (TABLE 14)
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.system_flags (
    id VARCHAR(50) PRIMARY KEY,
    flag_value BOOLEAN NOT NULL DEFAULT TRUE,
    state VARCHAR(50) NOT NULL DEFAULT 'CLOSED', -- 'CLOSED', 'OPEN', 'HALF_OPEN'
    failure_count INT NOT NULL DEFAULT 0,
    failure_threshold INT NOT NULL DEFAULT 5,
    cooldown_seconds INT NOT NULL DEFAULT 300,
    last_tripped_at TIMESTAMPTZ,
    config_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    description TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_system_flags_state CHECK (state IN ('CLOSED', 'OPEN', 'HALF_OPEN'))
);

CREATE TRIGGER trg_system_flags_updated_at
BEFORE UPDATE ON public.system_flags
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ====================================================================
-- 2. FACEBOOK SOURCES (TABLE 1)
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.facebook_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(100) UNIQUE NOT NULL, -- Page ID / Group ID
    source_type VARCHAR(50) NOT NULL DEFAULT 'PAGE',
    name VARCHAR(255) NOT NULL,
    url TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    auth_secret_ref TEXT, -- Reference key to credentials vault
    rate_limit_rpm INT NOT NULL DEFAULT 60,
    current_checkpoint_cursor TEXT, -- Incremental cursor / timestamp
    last_crawled_at TIMESTAMPTZ,
    consecutive_errors INT NOT NULL DEFAULT 0,
    last_error_code VARCHAR(100),
    last_error_message TEXT,
    circuit_breaker_tripped BOOLEAN NOT NULL DEFAULT FALSE,
    circuit_breaker_tripped_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_fb_sources_status CHECK (status IN (
        'ACTIVE', 'PAUSED', 'RATE_LIMITED', 'AUTH_ERROR', 
        'PERMISSION_ERROR', 'TEMP_ERROR', 'BLOCKED', 'DISABLED'
    ))
);

CREATE TRIGGER trg_fb_sources_updated_at
BEFORE UPDATE ON public.facebook_sources
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ====================================================================
-- 3. FACEBOOK RAW ITEMS - IMMUTABLE INGESTION (TABLE 2)
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.facebook_raw_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES public.facebook_sources(id) ON DELETE CASCADE,
    item_type VARCHAR(50) NOT NULL DEFAULT 'POST', -- 'POST', 'COMMENT', 'WEBHOOK_EVENT', 'BATCH_DUMP'
    external_item_id VARCHAR(100),
    payload_hash CHAR(64) UNIQUE NOT NULL, -- SHA-256 Hash to guarantee zero duplicate overwrite
    raw_payload JSONB NOT NULL,
    ingested_channel VARCHAR(50) NOT NULL DEFAULT 'WEBHOOK', -- 'WEBHOOK', 'GRAPH_API_POLL', 'MANUAL_IMPORT'
    processing_status VARCHAR(50) NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'PROCESSING', 'PROCESSED', 'FAILED', 'IGNORED'
    processing_attempts INT NOT NULL DEFAULT 0,
    max_retries INT NOT NULL DEFAULT 3,
    next_retry_at TIMESTAMPTZ,
    last_error TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    CONSTRAINT chk_raw_items_status CHECK (processing_status IN (
        'PENDING', 'PROCESSING', 'PROCESSED', 'FAILED', 'IGNORED'
    ))
);

-- ====================================================================
-- 4. FACEBOOK POSTS (TABLE 3)
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.facebook_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_item_id UUID REFERENCES public.facebook_raw_items(id) ON DELETE SET NULL,
    source_id UUID NOT NULL REFERENCES public.facebook_sources(id) ON DELETE CASCADE,
    post_id VARCHAR(100) UNIQUE NOT NULL,
    page_id VARCHAR(100) NOT NULL,
    author_id VARCHAR(100),
    author_name VARCHAR(255),
    message TEXT,
    permalink_url TEXT,
    created_time TIMESTAMPTZ NOT NULL,
    reactions_count INT NOT NULL DEFAULT 0,
    comments_count INT NOT NULL DEFAULT 0,
    shares_count INT NOT NULL DEFAULT 0,
    media_type VARCHAR(50) NOT NULL DEFAULT 'NONE',
    media_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_construction_related BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    crawled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_fb_posts_updated_at
BEFORE UPDATE ON public.facebook_posts
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ====================================================================
-- 5. FACEBOOK COMMENTS (TABLE 4)
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.facebook_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_item_id UUID REFERENCES public.facebook_raw_items(id) ON DELETE SET NULL,
    source_id UUID NOT NULL REFERENCES public.facebook_sources(id) ON DELETE CASCADE,
    post_id VARCHAR(100) NOT NULL,
    comment_id VARCHAR(100) UNIQUE NOT NULL,
    parent_comment_id VARCHAR(100),
    author_id VARCHAR(100),
    author_name VARCHAR(255),
    message TEXT NOT NULL,
    created_time TIMESTAMPTZ NOT NULL,
    like_count INT NOT NULL DEFAULT 0,
    is_hidden BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    crawled_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ====================================================================
-- 6. FACEBOOK PROCESSING JOBS (TABLE 5)
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.facebook_processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type VARCHAR(50) NOT NULL, -- 'INCREMENTAL_CRAWL', 'RAW_NORMALIZATION', 'INTENT_EXTRACTION', 'LEAD_DEDUP', 'DISPATCH'
    source_id UUID REFERENCES public.facebook_sources(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    items_total INT NOT NULL DEFAULT 0,
    items_processed INT NOT NULL DEFAULT 0,
    items_failed INT NOT NULL DEFAULT 0,
    checkpoint_before TEXT,
    checkpoint_after TEXT,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    execution_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_job_status CHECK (status IN (
        'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED'
    ))
);

-- ====================================================================
-- 7. FACEBOOK LEAD SIGNALS (TABLE 6)
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.facebook_lead_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_item_id UUID REFERENCES public.facebook_raw_items(id) ON DELETE SET NULL,
    source_id UUID NOT NULL REFERENCES public.facebook_sources(id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL, -- 'POST', 'COMMENT'
    entity_id VARCHAR(100) NOT NULL,
    post_id VARCHAR(100) NOT NULL,
    author_id VARCHAR(100),
    author_name VARCHAR(255),
    raw_text TEXT NOT NULL,
    intent VARCHAR(50) NOT NULL,
    product_category VARCHAR(100), -- 'ROBOT_XAY_DUNG', 'CAD_SOFTWARE', 'STRUCTURE_CSI', 'GEOTECH_PLAXIS', 'SURVEY_NDT', 'OTHER'
    product_mention VARCHAR(255),
    extracted_phones TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    extracted_emails TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    confidence_score NUMERIC(4,3) NOT NULL DEFAULT 1.000,
    extraction_method VARCHAR(50) NOT NULL DEFAULT 'HYBRID', -- 'REGEX_STRICT', 'QWEN_AI', 'HYBRID'
    ai_model VARCHAR(100),
    ai_prompt_version VARCHAR(50),
    signal_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'NEW', -- 'NEW', 'CONVERTED_TO_LEAD', 'DISCARDED', 'MERGED'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_signal_intent CHECK (intent IN (
        'IGNORE', 'INFORMATION', 'DISCUSSION', 'RECOMMENDATION',
        'RESEARCH', 'COMPARISON', 'LOOKING_TO_BUY', 'REQUEST_QUOTE',
        'LOOKING_FOR_SERVICE', 'URGENT_NEED', 'HIRING', 'PARTNERSHIP',
        'EXISTING_CUSTOMER'
    ))
);

-- ====================================================================
-- 8. CANONICAL LEADS (TABLE 7)
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    primary_phone VARCHAR(20),
    primary_email VARCHAR(255),
    full_name VARCHAR(255),
    company_name VARCHAR(255),
    customer_type VARCHAR(50) NOT NULL DEFAULT 'UNKNOWN',
    product_interest VARCHAR(255),
    product_group VARCHAR(100),
    primary_intent VARCHAR(50) NOT NULL DEFAULT 'REQUEST_QUOTE',
    status VARCHAR(50) NOT NULL DEFAULT 'NEW',
    resolution VARCHAR(50) NOT NULL DEFAULT 'NEW',
    lead_score INT NOT NULL DEFAULT 0,
    lead_tier VARCHAR(20) NOT NULL DEFAULT 'COLD', -- 'HOT', 'WARM', 'COLD'
    is_quote_requested BOOLEAN NOT NULL DEFAULT FALSE,
    assigned_to VARCHAR(100),
    last_contacted_at TIMESTAMPTZ,
    dedup_fingerprint CHAR(32) NOT NULL, -- MD5 hash of unique contact + product scope
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_leads_status CHECK (status IN (
        'NEW', 'CONTACTING', 'QUALIFIED', 'QUOTED',
        'NEGOTIATING', 'WON', 'LOST', 'SPAM'
    )),
    CONSTRAINT chk_leads_resolution CHECK (resolution IN (
        'NEW', 'POSSIBLE_DUPLICATE', 'EXISTING_LEAD', 'EXISTING_CUSTOMER'
    )),
    CONSTRAINT chk_leads_intent CHECK (primary_intent IN (
        'IGNORE', 'INFORMATION', 'DISCUSSION', 'RECOMMENDATION',
        'RESEARCH', 'COMPARISON', 'LOOKING_TO_BUY', 'REQUEST_QUOTE',
        'LOOKING_FOR_SERVICE', 'URGENT_NEED', 'HIRING', 'PARTNERSHIP',
        'EXISTING_CUSTOMER'
    )),
    CONSTRAINT chk_leads_tier CHECK (lead_tier IN ('HOT', 'WARM', 'COLD')),
    CONSTRAINT chk_leads_score CHECK (lead_score BETWEEN 0 AND 100)
);

CREATE TRIGGER trg_leads_updated_at
BEFORE UPDATE ON public.leads
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ====================================================================
-- 9. LEAD SOURCES (TABLE 8) - PROVENANCE MAPPER
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.lead_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES public.facebook_sources(id) ON DELETE CASCADE,
    signal_id UUID REFERENCES public.facebook_lead_signals(id) ON DELETE SET NULL,
    raw_item_id UUID REFERENCES public.facebook_raw_items(id) ON DELETE SET NULL,
    origin_type VARCHAR(50) NOT NULL, -- 'POST', 'COMMENT', 'MESSAGE'
    origin_external_id VARCHAR(100) NOT NULL,
    origin_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ====================================================================
-- 10. LEAD EVENTS (TABLE 9) - AUDIT TRAIL
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.lead_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL, -- 'LEAD_CREATED', 'SCORE_CALCULATED', 'STATUS_CHANGED', 'DISPATCHED_TELEGRAM', 'SYNCED_CRM', 'NOTE_ADDED'
    old_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    new_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    triggered_by VARCHAR(100) NOT NULL DEFAULT 'SYSTEM',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ====================================================================
-- 11. LEAD SCORES (TABLE 10) - SCORING DETAILS
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.lead_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    signal_id UUID REFERENCES public.facebook_lead_signals(id) ON DELETE SET NULL,
    intent_score INT NOT NULL DEFAULT 0,
    contact_score INT NOT NULL DEFAULT 0,
    profile_score INT NOT NULL DEFAULT 0,
    context_score INT NOT NULL DEFAULT 0,
    total_score INT NOT NULL CHECK (total_score BETWEEN 0 AND 100),
    tier VARCHAR(20) NOT NULL CHECK (tier IN ('HOT', 'WARM', 'COLD')),
    scoring_rules_applied JSONB NOT NULL DEFAULT '[]'::jsonb,
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ====================================================================
-- 12. FACEBOOK COLLECTION LOGS (TABLE 11)
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.facebook_collection_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES public.facebook_sources(id) ON DELETE SET NULL,
    job_id UUID REFERENCES public.facebook_processing_jobs(id) ON DELETE SET NULL,
    method VARCHAR(50) NOT NULL, -- 'GRAPH_API_POLL', 'WEBHOOK_RECEIVE', 'CSV_IMPORT'
    checkpoint_cursor_start TEXT,
    checkpoint_cursor_end TEXT,
    items_fetched INT NOT NULL DEFAULT 0,
    items_new INT NOT NULL DEFAULT 0,
    items_duplicated INT NOT NULL DEFAULT 0,
    http_status INT,
    duration_ms INT,
    rate_limit_usage_pct NUMERIC(5,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ====================================================================
-- 13. FACEBOOK ERRORS (TABLE 12) - ERROR REPOSITORY
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.facebook_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES public.facebook_sources(id) ON DELETE SET NULL,
    raw_item_id UUID REFERENCES public.facebook_raw_items(id) ON DELETE SET NULL,
    error_category VARCHAR(50) NOT NULL, -- 'RATE_LIMIT', 'AUTH_EXPIRED', 'PERMISSION_DENIED', 'UPSTREAM_AI_TIMEOUT', 'DATA_PARSE_ERROR', 'NETWORK_ERROR'
    error_code VARCHAR(100),
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    request_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    retry_count INT NOT NULL DEFAULT 0,
    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ====================================================================
-- 14. FACEBOOK SOURCE METRICS (TABLE 13)
-- ====================================================================
CREATE TABLE IF NOT EXISTS public.facebook_source_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES public.facebook_sources(id) ON DELETE CASCADE,
    metric_date DATE NOT NULL,
    total_posts_collected INT NOT NULL DEFAULT 0,
    total_comments_collected INT NOT NULL DEFAULT 0,
    total_leads_generated INT NOT NULL DEFAULT 0,
    total_hot_leads INT NOT NULL DEFAULT 0,
    total_errors INT NOT NULL DEFAULT 0,
    avg_latency_ms INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_source_metrics_date UNIQUE (source_id, metric_date)
);

CREATE TRIGGER trg_source_metrics_updated_at
BEFORE UPDATE ON public.facebook_source_metrics
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ====================================================================
-- 15. INDEXES (OPTIMIZED FOR QUERY & HIGH THROUGHPUT)
-- ====================================================================
CREATE INDEX IF NOT EXISTS idx_fb_sources_status ON public.facebook_sources(status);
CREATE INDEX IF NOT EXISTS idx_fb_sources_last_crawled ON public.facebook_sources(last_crawled_at);

CREATE INDEX IF NOT EXISTS idx_raw_items_source_status ON public.facebook_raw_items(source_id, processing_status);
CREATE INDEX IF NOT EXISTS idx_raw_items_hash ON public.facebook_raw_items(payload_hash);
CREATE INDEX IF NOT EXISTS idx_raw_items_retry ON public.facebook_raw_items(processing_status, next_retry_at) 
    WHERE processing_status IN ('PENDING', 'FAILED');

CREATE INDEX IF NOT EXISTS idx_fb_posts_source_created ON public.facebook_posts(source_id, created_time DESC);
CREATE INDEX IF NOT EXISTS idx_fb_posts_post_id ON public.facebook_posts(post_id);

CREATE INDEX IF NOT EXISTS idx_fb_comments_post_created ON public.facebook_comments(post_id, created_time ASC);
CREATE INDEX IF NOT EXISTS idx_fb_comments_author ON public.facebook_comments(author_id);

CREATE INDEX IF NOT EXISTS idx_lead_signals_intent ON public.facebook_lead_signals(intent);
CREATE INDEX IF NOT EXISTS idx_lead_signals_entity ON public.facebook_lead_signals(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_lead_signals_status ON public.facebook_lead_signals(status);

CREATE INDEX IF NOT EXISTS idx_leads_phone ON public.leads(primary_phone);
CREATE INDEX IF NOT EXISTS idx_leads_email ON public.leads(primary_email);
CREATE INDEX IF NOT EXISTS idx_leads_fingerprint ON public.leads(dedup_fingerprint);
CREATE INDEX IF NOT EXISTS idx_leads_tier_status ON public.leads(lead_tier, status);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON public.leads(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_lead_sources_lead_id ON public.lead_sources(lead_id);
CREATE INDEX IF NOT EXISTS idx_lead_events_lead_id ON public.lead_events(lead_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_lead_scores_lead_id ON public.lead_scores(lead_id);

CREATE INDEX IF NOT EXISTS idx_fb_errors_category ON public.facebook_errors(error_category, is_resolved);
CREATE INDEX IF NOT EXISTS idx_fb_errors_created_at ON public.facebook_errors(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_collection_logs_source_created ON public.facebook_collection_logs(source_id, created_at DESC);

-- ====================================================================
-- 16. SEED DATA FOR SYSTEM FLAGS (TABLE 14)
-- ====================================================================
INSERT INTO public.system_flags (id, flag_value, state, failure_threshold, cooldown_seconds, description)
VALUES 
    ('circuit_breaker_global', TRUE, 'CLOSED', 5, 300, 'Global circuit breaker protecting FB API and internal DB'),
    ('kill_switch_ingestion', FALSE, 'CLOSED', 0, 0, 'Emergency kill switch: when TRUE, instantly halts all FB ingestion'),
    ('qwen_ai_enabled', TRUE, 'CLOSED', 3, 180, 'Feature flag enabling Qwen AI for intent extraction and classification'),
    ('telegram_dispatch_enabled', TRUE, 'CLOSED', 5, 120, 'Feature flag enabling automated Telegram alerts for HOT/WARM leads'),
    ('google_sheets_sync_enabled', TRUE, 'CLOSED', 5, 120, 'Feature flag enabling Google Sheets / CRM sync')
ON CONFLICT (id) DO UPDATE SET 
    flag_value = EXCLUDED.flag_value,
    state = EXCLUDED.state,
    description = EXCLUDED.description,
    updated_at = NOW();

-- End of Migration
