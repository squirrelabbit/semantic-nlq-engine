CREATE OR REPLACE VIEW kikmix_history AS
SELECT
  code,
  admin_code,
  name,
  status,
  sgng_cd,
  is_sgng,
  sido_name,
  sigungu_name,
  eupmyeondong_name,
  dongri_name,
  created_at,
  abolished_at
FROM place_codes;

CREATE OR REPLACE FUNCTION place_codes_valid(p_date TEXT)
RETURNS TABLE (
  code TEXT,
  admin_code TEXT,
  name TEXT,
  status TEXT,
  sgng_cd TEXT,
  is_sgng BOOLEAN,
  sido_name TEXT,
  sigungu_name TEXT,
  eupmyeondong_name TEXT,
  dongri_name TEXT,
  created_at TEXT,
  abolished_at TEXT
)
LANGUAGE SQL
AS $$
  SELECT
    code,
    admin_code,
    name,
    status,
    sgng_cd,
    is_sgng,
    sido_name,
    sigungu_name,
    eupmyeondong_name,
    dongri_name,
    created_at,
    abolished_at
  FROM place_codes
  WHERE (created_at IS NULL OR created_at <= p_date)
    AND (abolished_at IS NULL OR abolished_at > p_date);
$$;
