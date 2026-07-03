# Ontology Tagging Rules

This document defines the semantic tags and mappings for the Sungnam population datasets.

## Core tags
- `std_ym`: 기준년월 (YYYYMM)
- `std_ymd`: 기준년월일 (YYYYMMDD)
- `time`: 시간 (HH)
- `hcode`: 행정동 코드
- `sgng_cd`: 시군구 코드
- `inflow_cd`: 유입지역 코드
- `sex_age`: 성연령 구분
- `x_coord`, `y_coord`: 좌표 (원본 좌표계 유지)

## Measure tags
- `h_pop`: 주거인구(야간체류지)
- `w_pop`: 직장인구(주간체류지)
- `v_pop`: 방문인구
- `time_00`..`time_23`: 시간대별 인구
- `m_0009`..`m_70u`: 남자 연령대 인구
- `w_0009`..`w_70u`: 여자 연령대 인구

## Dataset to class mapping
- `sungnam_service_inflow_pop` -> `ServiceInflowPop`
- `sungnam_service_sex_age_pop` -> `ServiceSexAgePop`
- `sungnam_service_pcell_sex_age_pop` -> `ServicePCellSexAgePop`
- `sungnam_service_pcell_pop` -> `ServicePCellPop`
- `sungnam_unique_pop` -> `UniquePop`

## Column mappings by table

### sungnam_service_inflow_pop
- Temporal: `std_ym`, `std_ymd`, `time`
- Location: `hcode`, `inflow_cd`
- Measures: `h_pop`, `w_pop`, `v_pop`

### sungnam_service_sex_age_pop
- Temporal: `std_ym`, `std_ymd`, `time`
- Location: `hcode`
- Dimension: `sex_age`
- Measures: `h_pop`, `w_pop`, `v_pop`

### sungnam_service_pcell_sex_age_pop
- Temporal: `std_ym`, `std_ymd`
- Location: `hcode`, `x_coord`, `y_coord`
- Measures: `m_0009`..`m_70u`, `w_0009`..`w_70u`

### sungnam_service_pcell_pop
- Temporal: `std_ym`, `std_ymd`
- Location: `hcode`, `x_coord`, `y_coord`
- Measures: `time_00`..`time_23`

### sungnam_unique_pop
- Temporal: `std_ym`, `std_ymd`
- Location: `sgng_cd`, `inflow_cd`
- Measures: `m_0009`..`m_70u`, `w_0009`..`w_70u`
