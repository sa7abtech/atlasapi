-- ATLAS Database Schema
-- Enable pgvector extension for vector embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Core knowledge base table with vector embeddings
CREATE TABLE IF NOT EXISTS atlas_core_knowledge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    content_hash TEXT UNIQUE NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    category TEXT,
    subcategory TEXT,
    source_file TEXT,
    chunk_index INTEGER,
    token_count INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Conversation history with embeddings
CREATE TABLE IF NOT EXISTS atlas_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    user_message TEXT NOT NULL,
    user_message_embedding VECTOR(1536),
    bot_response TEXT NOT NULL,
    context_chunks UUID[] DEFAULT ARRAY[]::UUID[],
    model_used TEXT,
    tokens_used INTEGER,
    response_time_ms INTEGER,
    language TEXT DEFAULT 'en',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User-specific learned facts and memory
CREATE TABLE IF NOT EXISTS atlas_client_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    fact_type TEXT NOT NULL, -- 'infrastructure', 'pain_point', 'preference', 'business_context'
    fact_key TEXT NOT NULL,
    fact_value TEXT NOT NULL,
    fact_embedding VECTOR(1536),
    confidence_score FLOAT DEFAULT 1.0,
    source_conversation_id UUID REFERENCES atlas_conversations(id),
    times_referenced INTEGER DEFAULT 0,
    last_referenced_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, fact_key)
);

-- Cached responses for common queries
CREATE TABLE IF NOT EXISTS atlas_insights_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash TEXT UNIQUE NOT NULL,
    query_text TEXT NOT NULL,
    query_embedding VECTOR(1536) NOT NULL,
    cached_response TEXT NOT NULL,
    language TEXT DEFAULT 'en',
    hit_count INTEGER DEFAULT 0,
    tokens_saved INTEGER DEFAULT 0,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_hit_at TIMESTAMP WITH TIME ZONE
);

-- User profiles and statistics
CREATE TABLE IF NOT EXISTS atlas_users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    preferred_language TEXT DEFAULT 'en',
    company_name TEXT,
    industry TEXT,
    total_conversations INTEGER DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    total_tokens_saved INTEGER DEFAULT 0,
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create indexes for vector similarity search
CREATE INDEX IF NOT EXISTS idx_core_knowledge_embedding
    ON atlas_core_knowledge USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_conversations_user_embedding
    ON atlas_conversations USING ivfflat (user_message_embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_client_memory_embedding
    ON atlas_client_memory USING ivfflat (fact_embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_insights_cache_embedding
    ON atlas_insights_cache USING ivfflat (query_embedding vector_cosine_ops)
    WITH (lists = 100);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON atlas_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON atlas_conversations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_client_memory_user_id ON atlas_client_memory(user_id);
CREATE INDEX IF NOT EXISTS idx_client_memory_fact_type ON atlas_client_memory(fact_type);
CREATE INDEX IF NOT EXISTS idx_core_knowledge_category ON atlas_core_knowledge(category);
CREATE INDEX IF NOT EXISTS idx_insights_cache_expires_at ON atlas_insights_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_insights_cache_query_hash ON atlas_insights_cache(query_hash);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
CREATE TRIGGER update_atlas_core_knowledge_updated_at
    BEFORE UPDATE ON atlas_core_knowledge
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_atlas_client_memory_updated_at
    BEFORE UPDATE ON atlas_client_memory
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to clean up expired cache entries
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS void AS $$
BEGIN
    DELETE FROM atlas_insights_cache WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Function to get relevant context for a query
CREATE OR REPLACE FUNCTION get_relevant_context(
    query_embedding VECTOR(1536),
    user_id_param BIGINT,
    limit_count INTEGER DEFAULT 3
)
RETURNS TABLE (
    content TEXT,
    category TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ck.content,
        ck.category,
        1 - (ck.embedding <=> query_embedding) AS similarity
    FROM atlas_core_knowledge ck
    ORDER BY ck.embedding <=> query_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get user memory facts
CREATE OR REPLACE FUNCTION get_user_memory(
    user_id_param BIGINT,
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    fact_type TEXT,
    fact_key TEXT,
    fact_value TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cm.fact_type,
        cm.fact_key,
        cm.fact_value
    FROM atlas_client_memory cm
    WHERE cm.user_id = user_id_param
    ORDER BY cm.last_referenced_at DESC NULLS LAST, cm.created_at DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Function to increment cache hit
CREATE OR REPLACE FUNCTION increment_cache_hit(query_hash_param TEXT)
RETURNS void AS $$
BEGIN
    UPDATE atlas_insights_cache
    SET
        hit_count = hit_count + 1,
        last_hit_at = NOW()
    WHERE query_hash = query_hash_param;
END;
$$ LANGUAGE plpgsql;

-- Function to update user statistics
CREATE OR REPLACE FUNCTION update_user_stats(
    user_id_param BIGINT,
    tokens_used INTEGER DEFAULT 0,
    tokens_saved INTEGER DEFAULT 0
)
RETURNS void AS $$
BEGIN
    INSERT INTO atlas_users (user_id, total_conversations, total_tokens_used, total_tokens_saved, last_seen_at)
    VALUES (user_id_param, 1, tokens_used, tokens_saved, NOW())
    ON CONFLICT (user_id) DO UPDATE SET
        total_conversations = atlas_users.total_conversations + 1,
        total_tokens_used = atlas_users.total_tokens_used + tokens_used,
        total_tokens_saved = atlas_users.total_tokens_saved + tokens_saved,
        last_seen_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Grant necessary permissions (adjust role name as needed)
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
-- GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO authenticated;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- Create a view for conversation analytics
CREATE OR REPLACE VIEW atlas_conversation_analytics AS
SELECT
    DATE_TRUNC('day', created_at) AS date,
    COUNT(*) AS total_conversations,
    COUNT(DISTINCT user_id) AS unique_users,
    AVG(tokens_used) AS avg_tokens_per_conversation,
    SUM(tokens_used) AS total_tokens_used,
    AVG(response_time_ms) AS avg_response_time_ms,
    COUNT(*) FILTER (WHERE model_used = 'gpt-4') AS gpt4_usage,
    COUNT(*) FILTER (WHERE model_used = 'gpt-3.5-turbo') AS gpt35_usage
FROM atlas_conversations
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY date DESC;

-- Function for vector similarity search (used by Python backend)
CREATE OR REPLACE FUNCTION match_knowledge(
    query_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.3,
    match_count INT DEFAULT 3
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    category TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        atlas_core_knowledge.id,
        atlas_core_knowledge.content,
        atlas_core_knowledge.category,
        1 - (atlas_core_knowledge.embedding <=> query_embedding) AS similarity
    FROM atlas_core_knowledge
    WHERE 1 - (atlas_core_knowledge.embedding <=> query_embedding) > match_threshold
    ORDER BY atlas_core_knowledge.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

COMMENT ON TABLE atlas_core_knowledge IS 'Core knowledge base with vector embeddings from strategic playbook';
COMMENT ON TABLE atlas_conversations IS 'Complete conversation history with embeddings for context retrieval';
COMMENT ON TABLE atlas_client_memory IS 'User-specific learned facts and preferences';
COMMENT ON TABLE atlas_insights_cache IS 'Cached responses for common queries to reduce costs';
COMMENT ON TABLE atlas_users IS 'User profiles and usage statistics';
