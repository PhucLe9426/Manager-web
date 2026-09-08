CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  email VARCHAR(190) NOT NULL UNIQUE,
  role VARCHAR(30) NOT NULL DEFAULT 'staff',
  password_hash TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customers (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(180) NOT NULL,
  contact_name VARCHAR(120),
  contact_email VARCHAR(190),
  contact_phone VARCHAR(30),
  service_plan VARCHAR(40) NOT NULL DEFAULT 'standard',
  status VARCHAR(30) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS websites (
  id BIGSERIAL PRIMARY KEY,
  customer_id BIGINT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  domain VARCHAR(253) NOT NULL,
  url TEXT NOT NULL UNIQUE,
  platform VARCHAR(50) NOT NULL DEFAULT 'wordpress',
  status VARCHAR(30) NOT NULL DEFAULT 'monitoring',
  performance_score SMALLINT,
  uptime_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
  ssl_expires_at TIMESTAMPTZ,
  last_checked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE websites ADD COLUMN IF NOT EXISTS wp_username VARCHAR(190);
ALTER TABLE websites ADD COLUMN IF NOT EXISTS wp_application_password TEXT;
ALTER TABLE websites ADD COLUMN IF NOT EXISTS wp_connected_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS monitoring_checks (
  id BIGSERIAL PRIMARY KEY,
  website_id BIGINT NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
  check_type VARCHAR(40) NOT NULL,
  status VARCHAR(30) NOT NULL,
  response_time_ms INTEGER,
  performance_score SMALLINT,
  lcp_seconds NUMERIC(6,2),
  cls_score NUMERIC(8,4),
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS maintenance_tasks (
  id BIGSERIAL PRIMARY KEY,
  website_id BIGINT NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
  title VARCHAR(240) NOT NULL,
  description TEXT,
  priority VARCHAR(30) NOT NULL DEFAULT 'medium',
  status VARCHAR(30) NOT NULL DEFAULT 'open',
  assignee_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
  due_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGSERIAL PRIMARY KEY,
  actor_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
  action VARCHAR(80) NOT NULL,
  entity_type VARCHAR(60) NOT NULL,
  entity_id VARCHAR(80) NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scan_jobs (
  id BIGSERIAL PRIMARY KEY,
  website_id BIGINT NOT NULL UNIQUE REFERENCES websites(id) ON DELETE CASCADE,
  status VARCHAR(30) NOT NULL DEFAULT 'queued',
  attempts INTEGER NOT NULL DEFAULT 0,
  scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  last_error TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_websites_customer ON websites(customer_id);
CREATE INDEX IF NOT EXISTS idx_websites_domain ON websites(domain);
CREATE INDEX IF NOT EXISTS idx_websites_status ON websites(status);
CREATE INDEX IF NOT EXISTS idx_checks_website_time ON monitoring_checks(website_id, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_checks_website_type_time ON monitoring_checks(website_id, check_type, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_status_due ON maintenance_tasks(status, due_at);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_scan_jobs_queue ON scan_jobs(status, scheduled_at);

CREATE TABLE IF NOT EXISTS wordpress_security_scans (
  id BIGSERIAL PRIMARY KEY,
  website_id BIGINT NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
  summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  results JSONB NOT NULL DEFAULT '{}'::jsonb,
  checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wp_security_scans_website_time
ON wordpress_security_scans(website_id, checked_at DESC);

CREATE TABLE IF NOT EXISTS malware_scans (
  id BIGSERIAL PRIMARY KEY,
  website_id BIGINT NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
  scan_type VARCHAR(20) NOT NULL DEFAULT 'quick',
  status VARCHAR(30) NOT NULL DEFAULT 'queued',
  cursor_position INTEGER NOT NULL DEFAULT 0,
  total_files INTEGER NOT NULL DEFAULT 0,
  scanned_files INTEGER NOT NULL DEFAULT 0,
  skipped_files INTEGER NOT NULL DEFAULT 0,
  info_count INTEGER NOT NULL DEFAULT 0,
  warning_count INTEGER NOT NULL DEFAULT 0,
  danger_count INTEGER NOT NULL DEFAULT 0,
  agent_version VARCHAR(30),
  rules_version VARCHAR(30),
  summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_malware_scans_queue ON malware_scans(status, created_at);
CREATE INDEX IF NOT EXISTS idx_malware_scans_website_time ON malware_scans(website_id, created_at DESC);

CREATE TABLE IF NOT EXISTS malware_findings (
  id BIGSERIAL PRIMARY KEY,
  scan_id BIGINT NOT NULL REFERENCES malware_scans(id) ON DELETE CASCADE,
  website_id BIGINT NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
  file_path TEXT NOT NULL,
  file_hash VARCHAR(64),
  component VARCHAR(40) NOT NULL DEFAULT 'unknown',
  rule_code VARCHAR(80) NOT NULL,
  severity VARCHAR(20) NOT NULL,
  title VARCHAR(240) NOT NULL,
  message TEXT NOT NULL,
  line_number INTEGER,
  snippet TEXT,
  status VARCHAR(30) NOT NULL DEFAULT 'open',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (scan_id, file_path, rule_code, line_number)
);

CREATE INDEX IF NOT EXISTS idx_malware_findings_scan_severity
ON malware_findings(scan_id, severity, status);

CREATE TABLE IF NOT EXISTS file_baselines (
  id BIGSERIAL PRIMARY KEY,
  website_id BIGINT NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
  file_path TEXT NOT NULL,
  file_hash VARCHAR(64) NOT NULL,
  source VARCHAR(40) NOT NULL DEFAULT 'internal',
  component VARCHAR(190),
  component_version VARCHAR(80),
  approved_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
  approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (website_id, file_path)
);
