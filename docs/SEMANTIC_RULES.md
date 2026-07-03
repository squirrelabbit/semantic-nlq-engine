# Semantic Rules (PoC 고정 규칙)

본 문서는 PoC에서 **고정되는 시맨틱 규칙**만 요약한다.

## 1) 허용 테이블
- `place_codes`
- `sungnam_service_inflow_pop`
- `sungnam_service_sex_age_pop`
- `sungnam_unique_pop`

## 2) 조인 규칙
- `sungnam_service_inflow_pop.hcode` → `place_codes.admin_code`
- `sungnam_service_inflow_pop.inflow_cd` → `place_codes.code`  
  - 필요 시 `LEFT(place_codes.code, 5)` 사용
- `sungnam_service_sex_age_pop.hcode` → `place_codes.admin_code`
- `sungnam_unique_pop.sgng_cd` → `place_codes.sgng_cd`
- `sungnam_unique_pop.inflow_cd` → `place_codes.code`  
  - 필요 시 `LEFT(place_codes.code, 5)` 사용

## 3) 행정 유효성 규칙
쿼리 시점(`std_ymd`) 기준으로 행정 코드 유효 여부를 필터링한다.
- `place_codes.created_at IS NULL OR place_codes.created_at <= '{std_ymd}'`
- `place_codes.abolished_at IS NULL OR place_codes.abolished_at >= '{std_ymd}'`

## 4) PII 마스킹
- 기준: **5 미만 값**
- 적용 대상: 인구/카운트 계열 컬럼 (`*_pop`, `*_cnt`, `m_*/w_*`)
- 출력 표기: `MASKED`

## 5) 안전 쿼리
- 허용: `SELECT` / `WITH`
- 금지: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `CREATE`
- 멀티 스테이트먼트(`;`) 금지

## 6) 실행 경로
- LLM 직접 DB 접근 금지
- MCP 도구를 통한 실행만 허용 (API 기본값)
