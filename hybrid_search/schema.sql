-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector for semantic search
CREATE EXTENSION IF NOT EXISTS pg_search;    -- ParadeDB for full-text search

-- Create loan_products table
CREATE TABLE IF NOT EXISTS loan_products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    loan_type VARCHAR(100) NOT NULL,           -- 주택담보대출, 신용대출, 전세자금대출 등
    min_amount DECIMAL(15, 2),                  -- 최소 대출금액
    max_amount DECIMAL(15, 2),                  -- 최대 대출금액
    min_rate DECIMAL(5, 2),                     -- 최저 금리 (%)
    max_rate DECIMAL(5, 2),                     -- 최고 금리 (%)
    loan_term_months INTEGER,                   -- 대출 기간 (개월)
    eligibility TEXT,                           -- 대출 자격 조건
    features TEXT[],                            -- 상품 특징
    bank_name VARCHAR(100),                     -- 은행명
    embedding vector(1536),                     -- text-embedding-3-small dimension
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for pgvector (cosine similarity)
CREATE INDEX IF NOT EXISTS idx_loan_products_embedding
ON loan_products USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create BM25 index for pg_search (ParadeDB)
-- This creates a full-text search index on name, description, loan_type, eligibility
CALL paradedb.create_bm25(
    index_name => 'idx_loan_products_bm25',
    table_name => 'loan_products',
    key_field => 'id',
    text_fields => paradedb.field('name', tokenizer => paradedb.tokenizer('korean')) ||
                   paradedb.field('description', tokenizer => paradedb.tokenizer('korean')) ||
                   paradedb.field('loan_type', tokenizer => paradedb.tokenizer('korean')) ||
                   paradedb.field('eligibility', tokenizer => paradedb.tokenizer('korean'))
);

-- Sample data for testing
INSERT INTO loan_products (name, description, loan_type, min_amount, max_amount, min_rate, max_rate, loan_term_months, eligibility, features, bank_name) VALUES
('내집마련 디딤돌 대출', '무주택 서민을 위한 저금리 주택구입자금 대출 상품입니다. 정부 지원으로 시중 금리보다 낮은 금리를 제공합니다.', '주택담보대출', 50000000, 500000000, 2.15, 3.00, 360, '무주택 세대주, 연소득 7천만원 이하, 주택가격 5억원 이하', ARRAY['정부지원', '저금리', '장기대출', '원리금균등상환'], '한국주택금융공사'),
('청년 전세자금 대출', '만 19세~34세 청년을 위한 전세자금 대출입니다. 보증금 최대 80%까지 지원하며 저금리 혜택을 제공합니다.', '전세자금대출', 10000000, 200000000, 1.80, 2.40, 24, '만 19세~34세, 무주택자, 연소득 5천만원 이하', ARRAY['청년특화', '저금리', '보증금80%', '온라인신청가능'], '주택도시보증공사'),
('직장인 신용대출', '재직 중인 직장인을 위한 무담보 신용대출 상품입니다. 신용등급에 따라 금리가 차등 적용됩니다.', '신용대출', 1000000, 100000000, 4.50, 12.00, 60, '재직 6개월 이상, 연소득 2천만원 이상', ARRAY['무담보', '빠른심사', '모바일신청', '중도상환수수료면제'], '신한은행'),
('자영업자 사업자금 대출', '개인사업자 및 소상공인을 위한 운영자금 대출입니다. 사업 실적에 따라 한도가 결정됩니다.', '사업자대출', 5000000, 300000000, 5.00, 10.00, 36, '사업자등록 1년 이상, 연매출 5천만원 이상', ARRAY['사업자전용', '운영자금', '시설자금', '유연한상환'], '기업은행'),
('햇살론 서민대출', '저신용·저소득 서민을 위한 정책서민금융 상품입니다. 연 10% 이내의 금리로 생활안정자금을 지원합니다.', '서민대출', 1000000, 30000000, 6.00, 10.00, 60, '연소득 4천5백만원 이하, 신용등급 6등급 이하', ARRAY['서민금융', '정책자금', '저신용가능', '채무조정연계'], '서민금융진흥원'),
('주택담보 생활자금 대출', '주택을 담보로 생활자금을 대출받는 상품입니다. 시세의 최대 70%까지 대출 가능합니다.', '주택담보대출', 10000000, 1000000000, 3.50, 6.00, 120, '주택 소유자, 담보물 시세 1억원 이상', ARRAY['담보대출', 'LTV70%', '생활자금', '만기일시상환가능'], '국민은행'),
('전문직 우대 신용대출', '의사, 변호사, 회계사 등 전문직 종사자를 위한 우대 금리 신용대출입니다.', '신용대출', 10000000, 200000000, 3.80, 7.00, 60, '전문직 자격증 보유, 개업 1년 이상', ARRAY['전문직우대', '고한도', '저금리', 'VIP서비스'], '우리은행'),
('신혼부부 전세대출', '결혼 7년 이내 신혼부부를 위한 전세자금 대출입니다. 특별 우대금리를 적용합니다.', '전세자금대출', 20000000, 300000000, 2.00, 3.50, 24, '결혼 7년 이내, 부부합산 연소득 1억원 이하, 무주택', ARRAY['신혼부부특화', '우대금리', '보증금90%', '자동갱신'], '하나은행'),
('중소기업 취업청년 대출', '중소기업에 재직 중인 청년을 위한 생활안정자금 대출입니다. 정부 이차보전으로 저금리 혜택을 제공합니다.', '신용대출', 5000000, 50000000, 1.50, 3.50, 60, '만 19세~34세, 중소기업 재직, 연소득 3천5백만원 이하', ARRAY['청년특화', '중소기업재직자', '이차보전', '원금만기일시상환'], '중소벤처기업진흥공단'),
('농어민 영농자금 대출', '농업, 어업, 축산업 종사자를 위한 영농자금 대출입니다. 농협과 연계하여 우대 조건을 제공합니다.', '사업자대출', 10000000, 500000000, 2.50, 5.00, 60, '농어업 종사자, 영농 경력 1년 이상', ARRAY['농어민전용', '영농자금', '저금리', '거치기간제공'], 'NH농협');
