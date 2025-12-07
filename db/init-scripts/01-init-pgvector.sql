-- Initialize pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Example table with vector column (uncomment and modify as needed)
-- CREATE TABLE IF NOT EXISTS embeddings (
--     id SERIAL PRIMARY KEY,
--     content TEXT,
--     embedding vector(1536),  -- Adjust dimension based on your embedding model
--     metadata JSONB,
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );

-- Create index for similarity search (uncomment when table is created)
-- CREATE INDEX ON embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
