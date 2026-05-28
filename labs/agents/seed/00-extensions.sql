-- Enable pgvector for the RAG sidebar (block 07).
-- The pgvector/pgvector image ships the extension binaries; we still have to
-- enable it inside the database.
CREATE EXTENSION IF NOT EXISTS vector;
