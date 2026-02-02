# Loan Products Hybrid Search CLI

pgvector(코사인 유사도)와 pg_search(ParadeDB BM25)를 RRF(Reciprocal Rank Fusion) 알고리즘으로 결합한 Python CLI입니다.

## Features

- **Semantic Search**: OpenAI `text-embedding-3-small`과 pgvector를 사용한 의미 기반 검색
- **Full-Text Search**: ParadeDB `pg_search`를 사용한 BM25 키워드 검색
- **Hybrid Search**: RRF 알고리즘으로 두 검색 결과를 최적으로 결합
- **가중치 조정**: Vector와 BM25 검색의 가중치를 조절 가능

## Requirements

- Python 3.10+
- Neon PostgreSQL with:
  - `pgvector` extension
  - `pg_search` extension (ParadeDB)
- OpenAI API key

## Installation

```bash
cd hybrid_search
pip install -r requirements.txt
```

## Configuration

`.env.example`을 `.env`로 복사하고 설정:

```bash
cp .env.example .env
```

```env
DATABASE_URL=postgresql://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
OPENAI_API_KEY=sk-your-api-key
```

## Database Setup

`schema.sql`을 실행하여 테이블과 인덱스 생성:

```bash
psql $DATABASE_URL -f schema.sql
```

## Usage

### Hybrid Search (RRF)

```bash
# 기본 하이브리드 검색
python cli.py search "청년 전세 대출"

# 상세 랭킹 정보 표시
python cli.py search "저금리 주택담보" --details

# 첫 번째 결과 상세 정보 표시
python cli.py search "신용대출" --show-first

# 가중치 조절 (vector 검색 강조)
python cli.py search "무주택자 대출" --vector-weight 1.5 --bm25-weight 0.8
```

### Vector Search Only

```bash
python cli.py vector "주택 구입 자금"
```

### BM25 Search Only

```bash
python cli.py bm25 "청년 전세"
```

### Compare Search Methods

```bash
python cli.py compare "청년 저금리 전세"
```

### Initialize Embeddings

```bash
python cli.py init-embeddings
```

### List All Products

```bash
python cli.py list-products
```

## RRF Algorithm

Reciprocal Rank Fusion은 여러 검색 결과를 결합하는 알고리즘입니다:

```
RRF_score(d) = Σ (weight_i / (k + rank_i(d)))
```

- `k`: 상수 (기본값 60)
- `rank_i(d)`: i번째 검색에서 문서 d의 순위
- `weight_i`: i번째 검색의 가중치

RRF의 장점:
- 스코어 정규화 불필요 (순위 기반)
- 여러 검색 결과를 공정하게 결합
- 파라미터 조정이 간단

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│  Query Input    │     │   OpenAI API    │
└────────┬────────┘     │ (embedding)     │
         │              └────────┬────────┘
         ▼                       ▼
┌─────────────────────────────────────────┐
│           Neon PostgreSQL               │
│  ┌─────────────┐   ┌─────────────┐     │
│  │  pgvector   │   │  pg_search  │     │
│  │  (cosine)   │   │   (BM25)    │     │
│  └──────┬──────┘   └──────┬──────┘     │
└─────────┼─────────────────┼─────────────┘
          │                 │
          ▼                 ▼
    ┌─────────────────────────────┐
    │      RRF Fusion             │
    │  score = Σ(w/(k+rank))      │
    └─────────────┬───────────────┘
                  │
                  ▼
    ┌─────────────────────────────┐
    │    Combined Results         │
    └─────────────────────────────┘
```
