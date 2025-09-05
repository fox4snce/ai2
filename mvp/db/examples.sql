-- Sample seed data for MVP IR Database
-- Demonstrates the core IR structure with tiny examples

-- Sample entities
INSERT INTO entity (id, type, alias_jsonb) VALUES
('E1', 'person', '{"aliases":["User"]}'),
('E2', 'expression', '{"text":"2+2"}'),
('E3', 'person', '{"aliases":["Alice","Alice Smith"]}'),
('E4', 'person', '{"aliases":["Bob","Bob Johnson"]}'),
('E5', 'location', '{"aliases":["Seattle","Seattle WA"]}');

-- Sample relations
INSERT INTO relation (id, src_id, rel_type, dst_id, attrs_jsonb) VALUES
('R1', 'E3', 'friend', 'E1', '{"since":"2023-01-01"}'),
('R2', 'E4', 'friend', 'E1', '{"since":"2023-02-15"}'),
('R3', 'E3', 'lives_in', 'E5', '{"verified":true}'),
('R4', 'E4', 'lives_in', 'E5', '{"verified":true}');

-- Sample modifiers
INSERT INTO modifier (id, target_kind, target_id, key, value, unit) VALUES
('M1', 'entity', 'E1', 'name', 'User', NULL),
('M2', 'entity', 'E2', 'complexity', 'simple', NULL),
('M3', 'relation', 'R1', 'closeness', 'high', 'scale');

-- Sample sources
INSERT INTO source (id, kind, uri, info_jsonb) VALUES
('S1', 'tool', 'EvalMath', '{"version":"1.0","reliability":"high"}'),
('S2', 'database', 'contacts.db', '{"last_updated":"2024-01-15"}'),
('S3', 'user_input', 'direct', '{"timestamp":"2024-01-20T10:30:00Z"}');

-- Sample events
INSERT INTO event (id, kind, at_time, payload_jsonb) VALUES
('EV1', 'user_utterance', CURRENT_TIMESTAMP, '{"text":"What is 2+2?"}'),
('EV2', 'tool_run', CURRENT_TIMESTAMP, '{"tool":"EvalMath","expr":"2+2"}'),
('EV3', 'obligation_created', CURRENT_TIMESTAMP, '{"type":"REPORT","payload":{"kind":"math","expr":"2+2"}}');

-- Sample assertions
INSERT INTO assertion (id, subject_id, predicate, object, confidence, source_id) VALUES
('A1', 'E2', 'evaluatesTo', '4', 1.0, 'S1'),
('A2', 'E3', 'is_friend', 'E1', 1.0, 'S2'),
('A3', 'E4', 'is_friend', 'E1', 1.0, 'S2'),
('A4', 'E3', 'lives_in', 'E5', 1.0, 'S2'),
('A5', 'E4', 'lives_in', 'E5', 1.0, 'S2');

-- Sample obligations
INSERT INTO obligation (id, kind, details_jsonb, status, event_id) VALUES
('OB1', 'REPORT', '{"kind":"math","expr":"2+2"}', 'resolved', 'EV1'),
('OB2', 'VERIFY', '{"target":"last_answer"}', 'resolved', 'EV1');

-- Sample tool runs
INSERT INTO tool_run (id, tool_name, inputs_jsonb, outputs_jsonb, status, duration_ms, event_id) VALUES
('TR1', 'EvalMath', '{"expr":"2+2"}', '{"result":4}', 'completed', 5, 'EV2');
