-- MVP IR Database Schema
-- Core tables for storing ideas, relations, and operations

-- Entities: people, docs, concepts, etc.
CREATE TABLE entity (
    id VARCHAR(50) PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    alias_jsonb JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Relations: typed edges between entities
CREATE TABLE relation (
    id VARCHAR(50) PRIMARY KEY,
    src_id VARCHAR(50) NOT NULL REFERENCES entity(id),
    rel_type VARCHAR(50) NOT NULL,
    dst_id VARCHAR(50) NOT NULL REFERENCES entity(id),
    attrs_jsonb JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Modifiers: attributes on entities/relations
CREATE TABLE modifier (
    id VARCHAR(50) PRIMARY KEY,
    target_kind VARCHAR(20) NOT NULL CHECK (target_kind IN ('entity', 'relation')),
    target_id VARCHAR(50) NOT NULL,
    key VARCHAR(50) NOT NULL,
    value TEXT,
    unit VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Assertions: claims about anything with confidence & provenance
CREATE TABLE assertion (
    id VARCHAR(50) PRIMARY KEY,
    subject_id VARCHAR(50) NOT NULL,
    predicate VARCHAR(100) NOT NULL,
    object TEXT NOT NULL,
    confidence DECIMAL(3,2) DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
    valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMP,
    source_id VARCHAR(50) REFERENCES source(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Events: something that occurred (question asked, tool run, etc.)
CREATE TABLE event (
    id VARCHAR(50) PRIMARY KEY,
    kind VARCHAR(50) NOT NULL,
    at_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payload_jsonb JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sources: where facts came from
CREATE TABLE source (
    id VARCHAR(50) PRIMARY KEY,
    kind VARCHAR(50) NOT NULL,
    uri TEXT,
    info_jsonb JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Obligations: active/resolved requirements
CREATE TABLE obligation (
    id VARCHAR(50) PRIMARY KEY,
    kind VARCHAR(50) NOT NULL,
    details_jsonb JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'resolved', 'failed', 'escalated')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_id VARCHAR(50) REFERENCES event(id)
);

-- Tool runs: execution records
CREATE TABLE tool_run (
    id VARCHAR(50) PRIMARY KEY,
    tool_name VARCHAR(100) NOT NULL,
    inputs_jsonb JSONB NOT NULL,
    outputs_jsonb JSONB,
    status VARCHAR(20) DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    duration_ms INTEGER,
    event_id VARCHAR(50) REFERENCES event(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_entity_type ON entity(type);
CREATE INDEX idx_relation_src ON relation(src_id);
CREATE INDEX idx_relation_dst ON relation(dst_id);
CREATE INDEX idx_relation_type ON relation(rel_type);
CREATE INDEX idx_assertion_subject ON assertion(subject_id);
CREATE INDEX idx_assertion_predicate ON assertion(predicate);
CREATE INDEX idx_event_kind ON event(kind);
CREATE INDEX idx_obligation_status ON obligation(status);
CREATE INDEX idx_tool_run_name ON tool_run(tool_name);
CREATE INDEX idx_tool_run_status ON tool_run(status);

-- Rules: logical/planning rules (Reasoning Engine)
CREATE TABLE rule (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    domain VARCHAR(50),
    head_jsonb JSONB NOT NULL,
    body_jsonb JSONB NOT NULL,
    enabled_bool BOOLEAN DEFAULT 1,
    version VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trajectories: reasoning/planning proof or plan steps
CREATE TABLE trajectory (
    id VARCHAR(50) PRIMARY KEY,
    run_id VARCHAR(50),
    steps_jsonb JSONB NOT NULL,
    start_context_jsonb JSONB,
    end_context_jsonb JSONB,
    metrics_jsonb JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);