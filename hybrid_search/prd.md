# PRD: Loan Products Hybrid Search CLI

## 개요

Neon PostgreSQL의 `loan_products` 테이블에서 pgvector(코사인 유사도)와 pg_search(ParadeDB BM25)를 RRF(Reciprocal Rank Fusion) 알고리즘으로 결합한 Python CLI 검색 도구입니다.

### 목적

- 대출 상품 검색 시 의미 기반 검색(Semantic Search)과 키워드 기반 검색(Full-Text Search)의 장점을 결합
- 사용자 쿼리의 의도를 더 정확하게 파악하여 관련성 높은 결과 제공
- 검색 품질 향상을 위한 가중치 조절 기능 제공

---

## 기술 스택

| 구성 요소 | 기술 | 용도 |
|-----------|------|------|
| Database | Neon PostgreSQL | 클라우드 PostgreSQL |
| Vector Search | pgvector | 코사인 유사도 기반 의미 검색 |
| Full-Text Search | pg_search (ParadeDB) | BM25 기반 키워드 검색 |
| Embedding | OpenAI text-embedding-3-small | 1536차원 벡터 임베딩 |
| CLI Framework | Click + Rich | 명령줄 인터페이스 |
| Language | Python 3.10+ | 구현 언어 |

---

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Query                                │
│                    "청년 전세 저금리 대출"                          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Python CLI (cli.py)                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Query Processing                       │    │
│  └─────────────────────────┬───────────────────────────────┘    │
└─────────────────────────────┼───────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│      OpenAI API         │     │                         │
│  text-embedding-3-small │     │                         │
│     (1536 dim)          │     │                         │
└───────────┬─────────────┘     │                         │
            │                   │                         │
            ▼                   ▼                         │
┌───────────────────────────────────────────────────────────────┐
│                    Neon PostgreSQL                             │
│  ┌─────────────────────┐     ┌─────────────────────┐          │
│  │     pgvector        │     │     pg_search       │          │
│  │  (Cosine Similarity)│     │      (BM25)         │          │
│  │                     │     │                     │          │
│  │  SELECT ... ORDER   │     │  SELECT ... WHERE   │          │
│  │  BY embedding <=>   │     │  id @@@ paradedb.   │          │
│  │  query_vector       │     │  parse(query)       │          │
│  └──────────┬──────────┘     └──────────┬──────────┘          │
│             │                           │                      │
│             │   Vector Results          │   BM25 Results       │
│             │   (with ranks)            │   (with ranks)       │
└─────────────┼───────────────────────────┼──────────────────────┘
              │                           │
              └─────────────┬─────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │     RRF Fusion Algorithm    │
              │                             │
              │  score = Σ (w / (k + rank)) │
              │                             │
              │  k = 60 (constant)          │
              │  w = weight per source      │
              └─────────────┬───────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │     Combined Results        │
              │   (sorted by RRF score)     │
              └─────────────────────────────┘
```

---

## RRF (Reciprocal Rank Fusion) 알고리즘

### 정의

여러 검색 결과 리스트를 단일 랭킹으로 결합하는 알고리즘입니다.

### 수식

```
RRF_score(d) = Σ (weight_i / (k + rank_i(d)))
```

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `k` | 순위 감쇠 상수 | 60 |
| `rank_i(d)` | i번째 검색에서 문서 d의 순위 (1-indexed) | - |
| `weight_i` | i번째 검색의 가중치 | 1.0 |

### 예시 계산

문서 A가 Vector Search에서 2위, BM25에서 5위인 경우:

```
RRF_score(A) = (1.0 / (60 + 2)) + (1.0 / (60 + 5))
             = 0.0161 + 0.0154
             = 0.0315
```

### RRF의 장점

| 장점 | 설명 |
|------|------|
| 스코어 정규화 불필요 | 순위 기반이므로 서로 다른 스코어 스케일 문제 없음 |
| 공정한 결합 | 각 검색 방법의 결과를 균형있게 반영 |
| 간단한 파라미터 | k값과 가중치만 조절하면 됨 |
| 견고함 | 하나의 검색 방법이 실패해도 다른 방법으로 보완 |

---

## 데이터베이스 스키마

### loan_products 테이블

```sql
CREATE TABLE loan_products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,           -- 상품명
    description TEXT NOT NULL,            -- 상품 설명
    loan_type VARCHAR(100) NOT NULL,      -- 대출 유형
    min_amount DECIMAL(15, 2),            -- 최소 대출금액
    max_amount DECIMAL(15, 2),            -- 최대 대출금액
    min_rate DECIMAL(5, 2),               -- 최저 금리 (%)
    max_rate DECIMAL(5, 2),               -- 최고 금리 (%)
    loan_term_months INTEGER,             -- 대출 기간 (개월)
    eligibility TEXT,                     -- 대출 자격 조건
    features TEXT[],                      -- 상품 특징
    bank_name VARCHAR(100),               -- 은행명
    embedding vector(1536),               -- 벡터 임베딩
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### 인덱스

| 인덱스 | 타입 | 용도 |
|--------|------|------|
| `idx_loan_products_embedding` | IVFFlat (pgvector) | 벡터 유사도 검색 |
| `idx_loan_products_bm25` | BM25 (ParadeDB) | 전문 검색 |

---

## 파일 구조

```
hybrid_search/
├── .env.example      # 환경 변수 템플릿
├── requirements.txt  # Python 의존성
├── schema.sql        # DB 스키마 및 샘플 데이터
├── cli.py            # 메인 CLI 애플리케이션
├── prd.md            # 제품 요구사항 문서 (본 문서)
└── README.md         # 사용 가이드
```

---

## CLI 명령어

### 1. Hybrid Search (RRF)

```bash
python cli.py search <query> [OPTIONS]
```

| 옵션 | 단축 | 기본값 | 설명 |
|------|------|--------|------|
| `--limit` | `-l` | 10 | 결과 개수 |
| `--vector-weight` | `-vw` | 1.0 | Vector 검색 가중치 |
| `--bm25-weight` | `-bw` | 1.0 | BM25 검색 가중치 |
| `--details` | `-d` | False | 상세 랭킹 표시 |
| `--show-first` | `-f` | False | 첫 번째 결과 상세 정보 |

**예시:**
```bash
# 기본 검색
python cli.py search "청년 전세 대출"

# Vector 검색 강조
python cli.py search "무주택자 저금리" --vector-weight 1.5 --bm25-weight 0.8

# 상세 정보 표시
python cli.py search "신용대출" --details --show-first
```

### 2. Vector Search Only

```bash
python cli.py vector <query> [--limit N]
```

pgvector 코사인 유사도만 사용하여 검색합니다.

### 3. BM25 Search Only

```bash
python cli.py bm25 <query> [--limit N]
```

ParadeDB BM25만 사용하여 검색합니다.

### 4. Compare Search Methods

```bash
python cli.py compare <query> [--limit N]
```

Vector, BM25, Hybrid(RRF) 검색 결과를 나란히 비교합니다.

### 5. Initialize Embeddings

```bash
python cli.py init-embeddings
```

임베딩이 없는 상품에 대해 text-embedding-3-small로 임베딩을 생성합니다.

### 6. List Products

```bash
python cli.py list-products
```

모든 대출 상품 목록과 임베딩 상태를 표시합니다.

---

## 설치 및 설정

### 1. 의존성 설치

```bash
cd hybrid_search
pip install -r requirements.txt
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일 편집:
```env
DATABASE_URL=postgresql://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
OPENAI_API_KEY=sk-your-api-key
```

### 3. 데이터베이스 초기화

```bash
psql $DATABASE_URL -f schema.sql
```

### 4. 임베딩 생성

```bash
python cli.py init-embeddings
```

---

## 사용 예시

### 기본 하이브리드 검색

```bash
$ python cli.py search "청년 전세 저금리" --details

Searching for: 청년 전세 저금리

Vector search: 10 results
BM25 search: 8 results

┏━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ # ┃ 상품명                  ┃ 유형       ┃ 은행          ┃ 금리       ┃ RRF Score  ┃ Vector Rank┃
┡━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ 1 │ 청년 전세자금 대출       │ 전세자금대출│ 주택도시보증공사│ 1.80~2.40% │ 0.0323     │ 1          │
│ 2 │ 신혼부부 전세대출        │ 전세자금대출│ 하나은행       │ 2.00~3.50% │ 0.0312     │ 2          │
│ 3 │ 중소기업 취업청년 대출   │ 신용대출    │ 중소벤처기업...│ 1.50~3.50% │ 0.0298     │ 3          │
│...│ ...                     │ ...        │ ...           │ ...        │ ...        │ ...        │
└───┴─────────────────────────┴────────────┴───────────────┴────────────┴────────────┴────────────┘
```

### 검색 방법 비교

```bash
$ python cli.py compare "주택 구입"

Comparing search methods for: 주택 구입

┏━━━┳━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ # ┃ Vector Search         ┃ BM25 Search           ┃ Hybrid (RRF)          ┃
┡━━━╇━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ 1 │ 내집마련 디딤돌 대출   │ 내집마련 디딤돌 대출   │ 내집마련 디딤돌 대출   │
│ 2 │ 주택담보 생활자금 대출 │ 주택담보 생활자금 대출 │ 주택담보 생활자금 대출 │
│ 3 │ 신혼부부 전세대출      │ 청년 전세자금 대출     │ 신혼부부 전세대출      │
└───┴───────────────────────┴───────────────────────┴───────────────────────┘

Hybrid (RRF) Score Breakdown:
  1. 내집마련 디딤돌 대출 | RRF: 0.0328 | V:1 B:1
  2. 주택담보 생활자금 대출 | RRF: 0.0317 | V:2 B:2
  3. 신혼부부 전세대출 | RRF: 0.0306 | V:3 B:4
```

---

## 성능 고려사항

### 인덱스 최적화

| 항목 | 권장 설정 | 설명 |
|------|-----------|------|
| IVFFlat lists | 100 | 데이터 크기에 따라 조정 (√n 권장) |
| probes | 10 | 정확도/속도 트레이드오프 |

### 검색 제한

- Vector/BM25 각각 `limit * 2`개를 가져와 RRF 융합
- 최종 결과는 `limit`개로 제한

---

## 향후 개선 사항

| 우선순위 | 기능 | 설명 |
|----------|------|------|
| P1 | 필터링 | 금리, 대출유형, 은행 등 조건 필터 |
| P1 | 캐싱 | 자주 사용되는 쿼리 임베딩 캐시 |
| P2 | 배치 임베딩 | 대량 데이터 임베딩 최적화 |
| P2 | A/B 테스트 | 가중치 최적화를 위한 실험 |
| P3 | API 서버 | FastAPI 기반 REST API |
| P3 | 모니터링 | 검색 품질 메트릭 수집 |

---

## 의존성

```txt
psycopg2-binary>=2.9.9
openai>=1.0.0
python-dotenv>=1.0.0
click>=8.1.0
rich>=13.0.0
numpy>=1.24.0
```

---

## 참고 자료

- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [ParadeDB pg_search](https://docs.paradedb.com/documentation/full-text-search)
- [RRF Paper](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [Neon PostgreSQL](https://neon.tech/docs)
