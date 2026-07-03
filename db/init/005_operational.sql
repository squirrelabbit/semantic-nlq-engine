CREATE TABLE IF NOT EXISTS knowledge_cards (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  tags JSONB DEFAULT '[]'::jsonb,
  summary TEXT NOT NULL,
  sources JSONB DEFAULT '[]'::jsonb,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS execution_logs (
  id BIGSERIAL PRIMARY KEY,
  request_id TEXT NOT NULL,
  original_question TEXT,
  generated_sql TEXT,
  execution_time DOUBLE PRECISION,
  error_message TEXT,
  status TEXT NOT NULL CHECK (status IN ('SUCCESS', 'FAIL')),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_execution_logs_request_id ON execution_logs (request_id);
CREATE INDEX IF NOT EXISTS idx_execution_logs_status ON execution_logs (status);
CREATE INDEX IF NOT EXISTS idx_execution_logs_created_at ON execution_logs (created_at);
