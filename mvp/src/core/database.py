"""
Core database layer for the IR (Idea Representation) system.

This module provides the database interface for storing and retrieving
entities, relations, assertions, events, and other IR components.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging
import threading

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """Represents an entity in the IR."""
    id: str
    type: str
    alias_jsonb: Optional[Dict] = None
    created_at: Optional[datetime] = None


@dataclass
class Relation:
    """Represents a relation between entities."""
    id: str
    src_id: str
    rel_type: str
    dst_id: str
    attrs_jsonb: Optional[Dict] = None
    created_at: Optional[datetime] = None


@dataclass
class Assertion:
    """Represents an assertion about something."""
    id: str
    subject_id: str
    predicate: str
    object: str
    rule_version: Optional[str] = None
    proof_ref: Optional[str] = None
    confidence: float = 1.0
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    source_id: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Event:
    """Represents an event that occurred."""
    id: str
    kind: str
    at_time: Optional[datetime] = None
    payload_jsonb: Optional[Dict] = None
    created_at: Optional[datetime] = None


@dataclass
class Source:
    """Represents a source of information."""
    id: str
    kind: str
    uri: Optional[str] = None
    info_jsonb: Optional[Dict] = None
    created_at: Optional[datetime] = None


@dataclass
class Obligation:
    """Represents an obligation to be satisfied."""
    id: str
    kind: str
    details_jsonb: Dict
    status: str = "active"
    created_at: Optional[datetime] = None
    event_id: Optional[str] = None


@dataclass
class ToolRun:
    """Represents a tool execution."""
    id: str
    tool_name: str
    inputs_jsonb: Dict
    outputs_jsonb: Optional[Dict] = None
    status: str = "running"
    duration_ms: Optional[int] = None
    event_id: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Rule:
    """Represents a reasoning/planning rule."""
    id: str
    name: str
    domain: Optional[str]
    head_jsonb: Dict
    body_jsonb: List[Dict]
    enabled_bool: bool = True
    version: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Trajectory:
    """Represents a reasoning/planning trajectory (proof or plan)."""
    id: str
    run_id: Optional[str]
    steps_jsonb: List[Dict]
    start_context_jsonb: Optional[Dict] = None
    end_context_jsonb: Optional[Dict] = None
    metrics_jsonb: Optional[Dict] = None
    created_at: Optional[datetime] = None


class IRDatabase:
    """Database interface for the IR system."""
    
    def __init__(self, db_path: str = ":memory:"):
        """Initialize the database connection."""
        self.db_path = db_path
        # Allow use across threads (FastAPI/TestClient/uvicorn)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # Basic concurrency pragmas
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA busy_timeout=3000")
        except Exception:
            pass
        # Serialize DB access across threads
        self._lock = threading.RLock()
        self._create_tables()
    
    def _create_tables(self):
        """Create the IR database tables."""
        with self._lock:
            cursor = self.conn.cursor()
            # Read and execute the schema
            with open("db/schema.sql", "r") as f:
                schema_sql = f.read()
            # Convert PostgreSQL syntax to SQLite
            schema_sql = schema_sql.replace("VARCHAR(50)", "TEXT")
            schema_sql = schema_sql.replace("VARCHAR(100)", "TEXT")
            schema_sql = schema_sql.replace("VARCHAR(20)", "TEXT")
            schema_sql = schema_sql.replace("JSONB", "TEXT")
            schema_sql = schema_sql.replace("DECIMAL(3,2)", "REAL")
            schema_sql = schema_sql.replace("TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "TEXT DEFAULT CURRENT_TIMESTAMP")
            schema_sql = schema_sql.replace("REFERENCES", "REFERENCES")
            # Remove PostgreSQL-specific constraints
            schema_sql = schema_sql.replace("CHECK (confidence >= 0 AND confidence <= 1)", "")
            schema_sql = schema_sql.replace("CHECK (status IN ('active', 'resolved', 'failed', 'escalated'))", "")
            schema_sql = schema_sql.replace("CHECK (status IN ('running', 'completed', 'failed'))", "")
            schema_sql = schema_sql.replace("CHECK (target_kind IN ('entity', 'relation'))", "")
            cursor.executescript(schema_sql)
            self.conn.commit()
    
    def create_entity(self, entity: Entity) -> str:
        """Create a new entity."""
        cursor = self.conn.cursor()
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
            INSERT INTO entity (id, type, alias_jsonb, created_at)
            VALUES (?, ?, ?, ?)
        """, (
                entity.id,
                entity.type,
                json.dumps(entity.alias_jsonb) if entity.alias_jsonb else None,
                entity.created_at or datetime.now().isoformat()
            ))
            self.conn.commit()
        return entity.id
    
    def create_relation(self, relation: Relation) -> str:
        """Create a new relation."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
            INSERT INTO relation (id, src_id, rel_type, dst_id, attrs_jsonb, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
                relation.id,
                relation.src_id,
                relation.rel_type,
                relation.dst_id,
                json.dumps(relation.attrs_jsonb) if relation.attrs_jsonb else None,
                relation.created_at or datetime.now().isoformat()
            ))
            self.conn.commit()
        return relation.id
    
    def create_assertion(self, assertion: Assertion) -> str:
        """Create a new assertion."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
            INSERT INTO assertion (id, subject_id, predicate, object, rule_version, proof_ref, confidence, 
                                 valid_from, valid_to, source_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
                assertion.id,
                assertion.subject_id,
                assertion.predicate,
                assertion.object,
                assertion.rule_version,
                assertion.proof_ref,
                assertion.confidence,
                assertion.valid_from.isoformat() if assertion.valid_from else None,
                assertion.valid_to.isoformat() if assertion.valid_to else None,
                assertion.source_id,
                assertion.created_at or datetime.now().isoformat()
            ))
            self.conn.commit()
        return assertion.id
    
    def create_event(self, event: Event) -> str:
        """Create a new event."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
            INSERT INTO event (id, kind, at_time, payload_jsonb, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
                event.id,
                event.kind,
                event.at_time.isoformat() if event.at_time else None,
                json.dumps(event.payload_jsonb) if event.payload_jsonb else None,
                event.created_at or datetime.now().isoformat()
            ))
            self.conn.commit()
        return event.id
    
    def create_source(self, source: Source) -> str:
        """Create a new source."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
            INSERT INTO source (id, kind, uri, info_jsonb, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
                source.id,
                source.kind,
                source.uri,
                json.dumps(source.info_jsonb) if source.info_jsonb else None,
                source.created_at or datetime.now().isoformat()
            ))
            self.conn.commit()
        return source.id
    
    def create_obligation(self, obligation: Obligation) -> str:
        """Create a new obligation."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
            INSERT INTO obligation (id, kind, details_jsonb, status, created_at, event_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
                obligation.id,
                obligation.kind,
                json.dumps(obligation.details_jsonb),
                obligation.status,
                obligation.created_at or datetime.now().isoformat(),
                obligation.event_id
            ))
            self.conn.commit()
        return obligation.id
    
    def create_tool_run(self, tool_run: ToolRun) -> str:
        """Create a new tool run."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
            INSERT INTO tool_run (id, tool_name, inputs_jsonb, outputs_jsonb, 
                                status, duration_ms, event_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
                tool_run.id,
                tool_run.tool_name,
                json.dumps(tool_run.inputs_jsonb),
                json.dumps(tool_run.outputs_jsonb) if tool_run.outputs_jsonb else None,
                tool_run.status,
                tool_run.duration_ms,
                tool_run.event_id,
                tool_run.created_at or datetime.now().isoformat()
            ))
            self.conn.commit()
        return tool_run.id

    def create_rule(self, rule: Rule) -> str:
        """Create a new rule."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(
            """
            INSERT INTO rule (id, name, domain, head_jsonb, body_jsonb, enabled_bool, version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                    rule.id,
                    rule.name,
                    rule.domain,
                    json.dumps(rule.head_jsonb),
                    json.dumps(rule.body_jsonb),
                    1 if rule.enabled_bool else 0,
                    rule.version,
                    rule.created_at or datetime.now().isoformat(),
                ),
            )
            self.conn.commit()
        return rule.id

    def create_trajectory(self, trajectory: Trajectory) -> str:
        """Create a new trajectory record."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(
            """
            INSERT INTO trajectory (id, run_id, steps_jsonb, start_context_jsonb, end_context_jsonb, metrics_jsonb, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                    trajectory.id,
                    trajectory.run_id,
                    json.dumps(trajectory.steps_jsonb),
                    json.dumps(trajectory.start_context_jsonb) if trajectory.start_context_jsonb else None,
                    json.dumps(trajectory.end_context_jsonb) if trajectory.end_context_jsonb else None,
                    json.dumps(trajectory.metrics_jsonb) if trajectory.metrics_jsonb else None,
                    trajectory.created_at or datetime.now().isoformat(),
                ),
            )
            self.conn.commit()
        return trajectory.id
    
    def get_assertions_by_subject(self, subject_id: str) -> List[Assertion]:
        """Get all assertions for a subject."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
            SELECT * FROM assertion WHERE subject_id = ?
        """, (subject_id,))
        rows = cursor.fetchall()
        assertions = []
        for row in rows:
            assertions.append(Assertion(
                id=row["id"],
                subject_id=row["subject_id"],
                predicate=row["predicate"],
                object=row["object"],
                rule_version=row["rule_version"] if "rule_version" in row.keys() else None,
                proof_ref=row["proof_ref"] if "proof_ref" in row.keys() else None,
                confidence=row["confidence"],
                valid_from=datetime.fromisoformat(row["valid_from"]) if row["valid_from"] else None,
                valid_to=datetime.fromisoformat(row["valid_to"]) if row["valid_to"] else None,
                source_id=row["source_id"],
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
            ))
        return assertions
    
    def get_obligations_by_status(self, status: str) -> List[Obligation]:
        """Get obligations by status."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
            SELECT * FROM obligation WHERE status = ?
        """, (status,))
        rows = cursor.fetchall()
        obligations = []
        for row in rows:
            obligations.append(Obligation(
                id=row["id"],
                kind=row["kind"],
                details_jsonb=json.loads(row["details_jsonb"]),
                status=row["status"],
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                event_id=row["event_id"]
            ))
        return obligations
    
    def update_obligation_status(self, obligation_id: str, status: str):
        """Update obligation status."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
            UPDATE obligation SET status = ? WHERE id = ?
        """, (status, obligation_id))
            self.conn.commit()
    
    def update_tool_run(self, tool_run_id: str, outputs: Dict, status: str, duration_ms: int):
        """Update tool run with results."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
            UPDATE tool_run SET outputs_jsonb = ?, status = ?, duration_ms = ?
            WHERE id = ?
        """, (json.dumps(outputs), status, duration_ms, tool_run_id))
            self.conn.commit()
    
    def close(self):
        """Close the database connection."""
        self.conn.close()
