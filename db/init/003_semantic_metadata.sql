CREATE TABLE IF NOT EXISTS semantic_metadata (
  id BIGSERIAL PRIMARY KEY,
  target_table TEXT NOT NULL UNIQUE,
  business_name TEXT,
  semantic_desc TEXT,
  join_rules JSONB,
  allowed_metrics TEXT[],
  constraints TEXT[],
  samples JSONB,
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
