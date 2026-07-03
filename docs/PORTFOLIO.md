# 행정 지능형 인구 분석 PoC 포트폴리오

이 문서는 본 프로젝트의 PoC 구현 범위와 실제 동작 구조를 **코드 기준으로** 정리한다.  
과장된 기능 설명을 피하고, 구현된 것과 미구현 범위를 명확히 구분한다.

## 1. 문제 정의
행정 데이터(유입/체류/방문 인구)를 **자연어 질문 → SQL → 결과 요약**으로 연결하고,  
누가 실행해도 같은 구조의 결과가 나오는 PoC 파이프라인을 구축한다.

## 2. PoC 범위 (In Scope)
- **데이터**: 성남시 인구 데이터 + 행정코드(KIKmix 기반)
- **기능**: NLQ 파이프라인(Planner → Coder → 실행 → 요약), 일일 리포트 JSON 생성
- **보안/운영 최소선**: Read-only SQL, PII 마스킹, 실행 로그
- **UI**: 질문 입력 → 결과 표/시각화 렌더링(웹앱)

## 3. 미구현/제외 (Out of Scope)
- 인증/권한, 캐싱, 운영 대시보드, 실시간 알림(Push)
- 본사업 규모의 대규모 데이터 확장 및 RAG/벡터 검색
- 자동 배치 운영(크론/스케줄러) 고도화

## 4. 시스템 구조 요약
- **Data Layer**: PostgreSQL + PostGIS
- **Semantic Layer**: `semantic/semantic_mapping.json`, `semantics/metrics.yaml`
- **Logic Layer**: L1/L2 Planner + Coder + Executor + Interpreter
- **Service Layer**: FastAPI API 서버 + webapp UI

## 5. 핵심 구현 포인트
1) **L1/L2 Planner**
   - L1에서 후보 테이블을 선택 → L2에서 상세 스키마 기반 최종 플랜 확정
   - 관련 코드: `agent/planner.py`, `agent/plan_l1_schema.json`, `agent/plan_schema.json`

2) **Semantic Constraints**
   - 테이블/컬럼/조인 규칙은 시맨틱 매핑으로 통제
   - 지표 의미 고정(`semantics/metrics.yaml`)으로 해석 오남용 방지
   - 관련 코드: `semantic/semantic_layer.py`, `semantic/metrics.py`

3) **Read-only SQL 실행**
   - MCP 도구를 통한 안전 실행 또는 direct 모드
   - 실행 전 SELECT/CTE 검증, 실패 시 1회 재시도(Self-healing)
   - 관련 코드: `agent/core.py`, `scripts/run_agent.py`

4) **PII 마스킹**
   - 5 미만 값은 결과에서 마스킹 처리
   - 관련 코드: `agent/core.py`, `scripts/run_agent.py`

5) **API/웹 UI**
   - `/api/nlq`로 질문 → SQL/결과/요약 응답
   - Mock 시나리오 JSON으로 데모 가능
   - 관련 코드: `api_server/app.py`, `webapp/src/App.tsx`

## 6. 데모 실행 흐름
1) API 서버 실행
   - `python api_server/app.py`
2) 질문 API 호출
   - `POST /api/nlq`
3) 응답 형식
   - `plan`, `sql`, `rows`, `insight`, `request_id`

## 7. 산출물 예시
- 실행 결과 JSON: `result_payload.json`
- 일일 리포트 예시: `reports/daily_report_YYYYMMDD.json`
- Mock 시나리오: `questions/mock_scenarios.json`

## 8. 기술 스택
- **Python**: LLM 플래닝/SQL 생성/실행
- **FastAPI**: API 서버
- **PostgreSQL + PostGIS**: 데이터 저장/검색
- **React**: UI

## 9. 한계와 다음 단계
- LLM 의존성(외부 API)과 비용/속도 이슈
- RAG 기반 테이블 선택, 캐싱, 운영 대시보드 미완
- 인증/권한 및 SLA 수준 운영 기능은 본사업 범위

## 10. 저장소 구조 요약
```
agent/           # Planner/Coder/Executor 핵심 로직
api_server/      # FastAPI 서버
semantic/        # 시맨틱 레이어 로직
semantics/       # metrics.yaml 등 지표 정의
questions/       # 질문 템플릿/Mock 시나리오
reports/         # 일일 리포트 결과
webapp/          # UI
```
