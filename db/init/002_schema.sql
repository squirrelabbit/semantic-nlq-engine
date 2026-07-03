CREATE TABLE IF NOT EXISTS sungnam_service_inflow_pop (
  id BIGSERIAL PRIMARY KEY,
  std_ym VARCHAR(6) NOT NULL,
  std_ymd VARCHAR(8) NOT NULL,
  time VARCHAR(2) NOT NULL,
  inflow_cd VARCHAR(10) NOT NULL,
  hcode VARCHAR(10) NOT NULL,
  h_pop NUMERIC(18, 2) NOT NULL,
  w_pop NUMERIC(18, 2) NOT NULL,
  v_pop NUMERIC(18, 2) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inflow_pop_std_ymd ON sungnam_service_inflow_pop (std_ymd);
CREATE INDEX IF NOT EXISTS idx_inflow_pop_hcode ON sungnam_service_inflow_pop (hcode);
CREATE INDEX IF NOT EXISTS idx_inflow_pop_inflow_cd ON sungnam_service_inflow_pop (inflow_cd);
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_inflow_pop'
  ) THEN
    ALTER TABLE sungnam_service_inflow_pop
      ADD CONSTRAINT uq_inflow_pop UNIQUE (std_ymd, time, inflow_cd, hcode);
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS sungnam_service_sex_age_pop (
  id BIGSERIAL PRIMARY KEY,
  std_ym VARCHAR(6) NOT NULL,
  std_ymd VARCHAR(8) NOT NULL,
  time VARCHAR(2) NOT NULL,
  sex_age VARCHAR(10) NOT NULL,
  hcode VARCHAR(10) NOT NULL,
  h_pop NUMERIC(18, 2) NOT NULL,
  w_pop NUMERIC(18, 2) NOT NULL,
  v_pop NUMERIC(18, 2) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sex_age_pop_std_ymd ON sungnam_service_sex_age_pop (std_ymd);
CREATE INDEX IF NOT EXISTS idx_sex_age_pop_hcode ON sungnam_service_sex_age_pop (hcode);
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_sex_age_pop'
  ) THEN
    ALTER TABLE sungnam_service_sex_age_pop
      ADD CONSTRAINT uq_sex_age_pop UNIQUE (std_ymd, time, sex_age, hcode);
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS sungnam_service_pcell_sex_age_pop (
  id BIGSERIAL PRIMARY KEY,
  std_ym VARCHAR(6) NOT NULL,
  std_ymd VARCHAR(8) NOT NULL,
  hcode VARCHAR(10) NOT NULL,
  m_0009 NUMERIC(38, 8) NOT NULL,
  m_1014 NUMERIC(38, 8) NOT NULL,
  m_1519 NUMERIC(18, 2) NOT NULL,
  m_2024 NUMERIC(18, 2) NOT NULL,
  m_2529 NUMERIC(18, 2) NOT NULL,
  m_3034 NUMERIC(18, 2) NOT NULL,
  m_3539 NUMERIC(18, 2) NOT NULL,
  m_4044 NUMERIC(18, 2) NOT NULL,
  m_4549 NUMERIC(18, 2) NOT NULL,
  m_5054 NUMERIC(18, 2) NOT NULL,
  m_5559 NUMERIC(18, 2) NOT NULL,
  m_6064 NUMERIC(18, 2) NOT NULL,
  m_6569 NUMERIC(18, 2) NOT NULL,
  m_7000 NUMERIC(18, 2) NOT NULL,
  w_0009 NUMERIC(18, 2) NOT NULL,
  w_1014 NUMERIC(18, 2) NOT NULL,
  w_1519 NUMERIC(18, 2) NOT NULL,
  w_2024 NUMERIC(18, 2) NOT NULL,
  w_2529 NUMERIC(18, 2) NOT NULL,
  w_3034 NUMERIC(18, 2) NOT NULL,
  w_3539 NUMERIC(18, 2) NOT NULL,
  w_4044 NUMERIC(18, 2) NOT NULL,
  w_4549 NUMERIC(18, 2) NOT NULL,
  w_5054 NUMERIC(18, 2) NOT NULL,
  w_5559 NUMERIC(18, 2) NOT NULL,
  w_6064 NUMERIC(18, 2) NOT NULL,
  w_6569 NUMERIC(18, 2) NOT NULL,
  w_7000 NUMERIC(18, 2) NOT NULL,
  x_coord NUMERIC(38, 8) NOT NULL,
  y_coord NUMERIC(38, 8) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pcell_sex_age_pop_std_ymd ON sungnam_service_pcell_sex_age_pop (std_ymd);
CREATE INDEX IF NOT EXISTS idx_pcell_sex_age_pop_hcode ON sungnam_service_pcell_sex_age_pop (hcode);
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_pcell_sex_age_pop'
  ) THEN
    ALTER TABLE sungnam_service_pcell_sex_age_pop
      ADD CONSTRAINT uq_pcell_sex_age_pop UNIQUE (std_ymd, hcode, x_coord, y_coord);
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS sungnam_service_pcell_pop (
  id BIGSERIAL PRIMARY KEY,
  std_ym VARCHAR(6) NOT NULL,
  std_ymd VARCHAR(8) NOT NULL,
  hcode VARCHAR(10) NOT NULL,
  time_00 NUMERIC(18, 2) NOT NULL,
  time_01 NUMERIC(18, 2) NOT NULL,
  time_02 NUMERIC(18, 2) NOT NULL,
  time_03 NUMERIC(18, 2) NOT NULL,
  time_04 NUMERIC(18, 2) NOT NULL,
  time_05 NUMERIC(18, 2) NOT NULL,
  time_06 NUMERIC(18, 2) NOT NULL,
  time_07 NUMERIC(18, 2) NOT NULL,
  time_08 NUMERIC(18, 2) NOT NULL,
  time_09 NUMERIC(18, 2) NOT NULL,
  time_10 NUMERIC(18, 2) NOT NULL,
  time_11 NUMERIC(18, 2) NOT NULL,
  time_12 NUMERIC(18, 2) NOT NULL,
  time_13 NUMERIC(18, 2) NOT NULL,
  time_14 NUMERIC(18, 2) NOT NULL,
  time_15 NUMERIC(18, 2) NOT NULL,
  time_16 NUMERIC(18, 2) NOT NULL,
  time_17 NUMERIC(18, 2) NOT NULL,
  time_18 NUMERIC(18, 2) NOT NULL,
  time_19 NUMERIC(18, 2) NOT NULL,
  time_20 NUMERIC(18, 2) NOT NULL,
  time_21 NUMERIC(18, 2) NOT NULL,
  time_22 NUMERIC(18, 2) NOT NULL,
  time_23 NUMERIC(18, 2) NOT NULL,
  x_coord NUMERIC(38, 8) NOT NULL,
  y_coord NUMERIC(38, 8) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pcell_pop_std_ymd ON sungnam_service_pcell_pop (std_ymd);
CREATE INDEX IF NOT EXISTS idx_pcell_pop_hcode ON sungnam_service_pcell_pop (hcode);
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_pcell_pop'
  ) THEN
    ALTER TABLE sungnam_service_pcell_pop
      ADD CONSTRAINT uq_pcell_pop UNIQUE (std_ymd, hcode, x_coord, y_coord);
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS sungnam_unique_pop (
  id BIGSERIAL PRIMARY KEY,
  std_ym VARCHAR(6) NOT NULL,
  std_ymd VARCHAR(8) NOT NULL,
  sgng_cd VARCHAR(5) NOT NULL,
  inflow_cd VARCHAR(5) NOT NULL,
  m_0009 NUMERIC(38, 8) NOT NULL,
  m_1014 NUMERIC(18, 2) NOT NULL,
  m_1519 NUMERIC(18, 2) NOT NULL,
  m_2024 NUMERIC(18, 2) NOT NULL,
  m_2529 NUMERIC(18, 2) NOT NULL,
  m_3034 NUMERIC(18, 2) NOT NULL,
  m_3539 NUMERIC(18, 2) NOT NULL,
  m_4044 NUMERIC(18, 2) NOT NULL,
  m_4549 NUMERIC(18, 2) NOT NULL,
  m_5054 NUMERIC(18, 2) NOT NULL,
  m_5559 NUMERIC(18, 2) NOT NULL,
  m_6064 NUMERIC(18, 2) NOT NULL,
  m_6569 NUMERIC(18, 2) NOT NULL,
  m_70u NUMERIC(18, 2) NOT NULL,
  w_0009 NUMERIC(18, 2) NOT NULL,
  w_1014 NUMERIC(18, 2) NOT NULL,
  w_1519 NUMERIC(18, 2) NOT NULL,
  w_2024 NUMERIC(18, 2) NOT NULL,
  w_2529 NUMERIC(18, 2) NOT NULL,
  w_3034 NUMERIC(18, 2) NOT NULL,
  w_3539 NUMERIC(18, 2) NOT NULL,
  w_4044 NUMERIC(18, 2) NOT NULL,
  w_4549 NUMERIC(18, 2) NOT NULL,
  w_5054 NUMERIC(18, 2) NOT NULL,
  w_5559 NUMERIC(18, 2) NOT NULL,
  w_6064 NUMERIC(18, 2) NOT NULL,
  w_6569 NUMERIC(18, 2) NOT NULL,
  w_70u NUMERIC(18, 2) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_unique_pop_std_ymd ON sungnam_unique_pop (std_ymd);
CREATE INDEX IF NOT EXISTS idx_unique_pop_sgng_cd ON sungnam_unique_pop (sgng_cd);
CREATE INDEX IF NOT EXISTS idx_unique_pop_inflow_cd ON sungnam_unique_pop (inflow_cd);
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_unique_pop'
  ) THEN
    ALTER TABLE sungnam_unique_pop
      ADD CONSTRAINT uq_unique_pop UNIQUE (std_ymd, sgng_cd, inflow_cd);
  END IF;
END $$;
