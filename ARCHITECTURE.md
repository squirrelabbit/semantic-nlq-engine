# 행정 지능형 인구 분석 플랫폼 개발 아키텍처

*(Detailed Architecture)*

본 문서는 경기도 인구 데이터 분석 플랫폼의 시스템 아키텍처를 정의한다.
본 시스템은 **LLM의 유연성**과 **정형 데이터의 무결성**을 결합한 **Semantic-Driven Agent 구조**를 채택한다.

---

## 1. 전체 시스템 구성도 (System Overview)

시스템은 **4개의 독립된 레이어**로 구성되며, 각 레이어는 **MCP(Model Context Protocol)** 를 통해 느슨하게 결합(Loosely Coupled)되어 보안과 확장성을 확보한다.

---

## 1.1 레이어별 아키텍처

### Data Layer (Storage & Search)

* **PostgreSQL 16 + PostGIS**

  * 민간/공공 정형 데이터 저장
  * 공간 연산 및 행정구역 기반 분석 처리
* **Vector DB (pgvector)**

  * 지역 지식 카드(Knowledge Cards)
  * 보고서 템플릿 RAG 검색

---

### Semantic Layer (Knowledge Context)

* **Metadata Registry**

  * 테이블 스키마
  * 조인 경로
  * 컬럼 비즈니스 정의 관리
* **Administrative Logic**

  * 행정구역 변경 이력(KIKmix)
  * 행정 코드 보정 로직 처리

---

### Logic Layer (AI Agent Pipeline)

* **Planner**

  * 질문 의도 파악
  * 데이터 가용성 및 분석 전략 수립
* **Coder (Text-to-SQL)**

  * 시맨틱 제약 조건을 준수하는 무결성 SQL 생성
* **Executor & Interpreter**

  * SQL 실행 결과 정제
  * 행정 문서 스타일의 통찰 도출

---

### Service Layer (Interface)

* **Push Engine**

  * 새벽 배치 작업
  * 자동 브리핑 및 알림 발송
* **Interactive UI**

  * React 기반 대시보드
  * 드릴다운 분석 도구

---

## 2. 핵심 에이전트 파이프라인 (Agent Workflow)

사용자의 자연어 질문은 다음의 **5-Step Pipeline**을 통해 결과로 변환된다.

---

### Step 1. Intent Analysis & Planning (Planner)

**Input**

* 사용자 질문

  * 예: “지난 3년간 판교 유입 추이 보여줘”

**Task**

* 질문의 시계열성 여부 판단
* 필요 지표 정의

**Semantic Fetch**

* 질문과 관련된 테이블 정보(인구 데이터, 지역 지식 카드)를 시맨틱 레이어에서 조회

#### Data Discovery Loop

*(효율적 토큰 관리 및 정확도 향상)*

1. **L1 요약 확인**

   * 전체 도메인 및 테이블 요약 정보를 스캔하여 탐색 범위 최소화
2. **관련 테이블 선택**

   * 질문 맥락에 가장 부합하는 후보 테이블을 식별하여 불필요한 컨텍스트 주입 방지
3. **L2 상세 요청**

   * 선택된 테이블의 상세 스키마(컬럼, 조인, 제약, 샘플 데이터) 로딩
4. **최종 플랜 확정**

   * 실행 가능한 분석 경로를 확정하여 할루시네이션(Hallucination) 최소화

---

### Step 2. Constrained SQL Generation (Coder)

* **Constraint Injection**

  * `abolished_at IS NULL`
  * KIKmix 매핑 규칙 등 행정 제약 조건 강제 주입
* **Table Selection**

  * 기간 분석 요청 시 원천 테이블 대신 요약 테이블(Summary Table) 우선 선택
* **Validation**

  * SQL 문법 검증
  * Read-only 권한 준수 여부 사전 검토

---

### Step 3. Secure Execution (Executor)

* **MCP Protocol**

  * LLM은 DB에 직접 접근하지 않음
  * MCP 도구를 통해 사전 정의된 파라미터로 SQL 실행
* **Error Handling**

  * 쿼리 실패 시 에러 메시지를 Coder에 피드백
  * Self-healing(SQL 재작성) 시도

---

### Step 4. Contextual Interpretation (Interpreter)

* **Data Synthesis**

  * 결과값 기반 통계적 이상치(Anomaly) 탐지
* **Knowledge Fusion**

  * 결과 수치와 지역 지식 카드(Knowledge Cards)를 결합하여 현상 발생 원인 설명
* **Tone & Manner**

  * 공무원 보고서 전용 프롬프트 적용
  * 정중하고 객관적인 문체 유지

---

### Step 5. Final Delivery

* **Visualization**

  * 데이터 성격에 맞는 차트 자동 추천

    * Bar / Line / Heatmap
* **HWP Formatting**

  * 한글(HWP) 보고서 복사용 텍스트 정제 제공

---

## 3. 데이터 및 시맨틱 레이어 설계

*(Database & Semantic Schema)*

---

### 3.1 시맨틱 메타데이터 구조 (Semantic Metadata Table)

본 레이어는 **분석팀이 관리**하며, **에이전트는 해당 데이터를 참조하여 동작**한다.

| Column          | Type    | Description                 |
| --------------- | ------- | --------------------------- |
| target_table    | VARCHAR | 분석 대상 물리 테이블명               |
| business_name   | VARCHAR | 공무원이 이해할 수 있는 테이블 별칭        |
| semantic_desc   | TEXT    | LLM 데이터 해석 가이드              |
| join_rules      | JSONB   | 조인 가능 키 및 조건 정의             |
| allowed_metrics | ARRAY   | 집계 가능한 컬럼 및 수식 (sum, avg 등) |

---

### 3.1.1 계층형 요약 구조 (L1 / L2)

플래너의 토큰 효율성과 분석 정확도를 확보하기 위해 지식을 계층화한다.

* **L1 Domain Map**

  * 도메인별 핵심 테이블 목록
  * 광범위한 탐색을 위한 요약 정보
* **L2 Detail Schema**

  * 컬럼
  * 조인 규칙
  * 제약 조건
  * 샘플 데이터

**적용 원칙**
Planner는 L1을 통해 후보를 좁히고, L2를 요청하여 최종 분석 플랜을 확정한다.

---

### 3.2 행정구역 이력 관리 (Administrative History)

* **Master Table**

  * `kikmix_history`
* **Logic**

  * 특정 시점 기준 조회 시

    * 해당 시점의 유효 코드와 현재 코드 간 매핑
  * View 또는 동적 매핑 테이블 활용

---

## 4. 인프라 및 운영 전략 (Infra & Operation)

---

### 4.1 Push 브리핑 스케줄링 (Batch Process)

* **Trigger**

  * 매일 새벽 05:00
  * SKT 전일 데이터 적재 완료 시점
* **Pipeline**

  * 사전 정의된 핵심 KPI 질문 자동 실행
* **Caching**

  * 생성된 리포트를 Redis 또는 별도 스토리지에 캐싱
  * 사용자 요청 시 즉시 응답

---

### 4.2 Auto-Discovery (Data Expansion)

* **Monitoring**

  * DB `information_schema` 상시 감시
* **AI Metadata Draft**

  * 신규 테이블 발견 시
  * LLM이 샘플 데이터를 기반으로 시맨틱 초안 생성
* **Approval Loop**

  * 관리자(분석팀) 승인 후 Planner 지식 저장소에 반영

---

## 5. 보안 및 신뢰성 정책 (Security & Reliability)

* **Security**

  * DB 접근은 Read-only 계정으로 제한
* **PII 보호**

  * 최소 집계 단위 기준 마스킹 처리
  * 예: 격자 내 5인 미만
* **Reliability Score**

  * SQL 실행 성공률
  * 행정 코드 보정률
  * 데이터 최신성 종합 점수 제공
* **출처 명시**

  * Interpreter 결과에 Source Data 필수 표기

---

## 6. 비용 및 시각화 최적화 전략

*(Optimization & Visualization)*

실시간 분석의 운영 지속성을 확보하기 위해 비용을 통제하고 사용자 경험을 극대화한다.

---

### 6.1 LLM 비용 최적화 (Cost Management)

* **Model Tiering**

  * 질문 분류(L1)는 경량 모델
  * 복잡한 SQL 생성(L2)은 고성능 모델
  * 하이브리드 라우팅 적용
* **Prompt Caching**

  * 반복되는 시맨틱 메타데이터 주입 시 프롬프트 캐싱 활성화
  * 토큰 과금 절감
* **Result Caching**

  * 동일 조건 반복 질문에 대해 Redis 캐시 결과 우선 반환
  * LLM 호출 최소화

---

### 6.2 동적 시각화 추천 로직 (Dynamic Visualization)

* **Shape-based Selection**

  * 결과 데이터 구조(시계열, 공간 정보 등)를 분석하여 최적 차트 자동 추천
* **Semantic Hint**

  * 지표별 선호 시각화 방식(`preferred_visual`)을 사전 정의
  * 분석 의도에 부합하는 시각화 제공

---

## 결론 (Project Conclusion)

본 아키텍처는 **유연한 시맨틱 레이어**와 **계층형 지식 구조**를 통해 공공 데이터 분석의 한계를 극복하고,
**데이터 지능화(Data Intelligence)** 를 실현하는 **미래형 행정 플랫폼의 표준 아키텍처**를 제시한다.
