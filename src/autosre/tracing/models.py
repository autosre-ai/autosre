"""
Tracing data models for AutoSRE V2.

Provides canonical representations for distributed tracing concepts:
- Spans and traces
- Context propagation
- Resources and instrumentation
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict, field_validator


class SpanKind(str, Enum):
    """Type of span based on its role in the trace."""
    
    INTERNAL = "internal"  # Internal operation, not an RPC
    SERVER = "server"  # Server side of an RPC
    CLIENT = "client"  # Client side of an RPC
    PRODUCER = "producer"  # Message producer
    CONSUMER = "consumer"  # Message consumer
    UNSPECIFIED = "unspecified"


class SpanStatus(str, Enum):
    """Status of a span's operation."""
    
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class SpanEvent:
    """
    An event occurring during a span's lifetime.
    
    Events are timestamped annotations with optional attributes.
    """
    
    name: str
    timestamp: datetime
    attributes: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.timestamp.isoformat(),
            "attributes": self.attributes,
        }


@dataclass
class SpanLink:
    """
    A link to another span.
    
    Links can represent batch operations or causal relationships.
    """
    
    trace_id: str
    span_id: str
    attributes: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "attributes": self.attributes,
        }


@dataclass
class Resource:
    """
    Resource information describing the entity producing spans.
    
    Typically includes service name, version, host info, etc.
    """
    
    service_name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    
    @property
    def service_namespace(self) -> Optional[str]:
        return self.attributes.get("service.namespace")
    
    @property
    def service_version(self) -> Optional[str]:
        return self.attributes.get("service.version")
    
    @property
    def host_name(self) -> Optional[str]:
        return self.attributes.get("host.name")
    
    @property
    def k8s_namespace(self) -> Optional[str]:
        return self.attributes.get("k8s.namespace.name")
    
    @property
    def k8s_pod(self) -> Optional[str]:
        return self.attributes.get("k8s.pod.name")
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "service_name": self.service_name,
            "attributes": self.attributes,
        }


@dataclass
class InstrumentationScope:
    """
    Instrumentation scope (library/package that created the span).
    """
    
    name: str
    version: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "attributes": self.attributes,
        }


@dataclass
class TraceContext:
    """
    Trace context for propagation.
    
    Implements W3C Trace Context format.
    """
    
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    trace_flags: int = 0
    trace_state: str = ""
    
    @property
    def is_sampled(self) -> bool:
        """Check if trace is sampled."""
        return (self.trace_flags & 0x01) != 0
    
    def to_traceparent(self) -> str:
        """Generate W3C traceparent header value."""
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags:02x}"
    
    @classmethod
    def from_traceparent(cls, value: str) -> "TraceContext":
        """Parse W3C traceparent header value."""
        parts = value.split("-")
        if len(parts) != 4:
            raise ValueError(f"Invalid traceparent: {value}")
        
        version, trace_id, span_id, flags = parts
        return cls(
            trace_id=trace_id,
            span_id=span_id,
            trace_flags=int(flags, 16),
        )


class Span(BaseModel):
    """
    A single span in a distributed trace.
    
    Represents a single unit of work or operation in a system.
    """
    
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    # Identity
    trace_id: str = Field(..., description="Unique trace identifier (32 hex chars)")
    span_id: str = Field(..., description="Unique span identifier (16 hex chars)")
    parent_span_id: Optional[str] = Field(default=None, description="Parent span ID")
    
    # Naming
    name: str = Field(..., description="Span name (operation)")
    kind: SpanKind = Field(default=SpanKind.INTERNAL)
    
    # Timing
    start_time: datetime = Field(..., description="Span start time")
    end_time: datetime = Field(..., description="Span end time")
    
    # Status
    status: SpanStatus = Field(default=SpanStatus.UNSET)
    status_message: str = Field(default="")
    
    # Attributes
    attributes: dict[str, Any] = Field(default_factory=dict)
    
    # Events and Links
    events: list[dict[str, Any]] = Field(default_factory=list)
    links: list[dict[str, Any]] = Field(default_factory=list)
    
    # Resource and Scope
    resource: dict[str, Any] = Field(default_factory=dict)
    scope: dict[str, Any] = Field(default_factory=dict)
    
    @property
    def duration_ms(self) -> float:
        """Get span duration in milliseconds."""
        return (self.end_time - self.start_time).total_seconds() * 1000
    
    @property
    def duration(self) -> timedelta:
        """Get span duration as timedelta."""
        return self.end_time - self.start_time
    
    @property
    def is_root(self) -> bool:
        """Check if this is a root span (no parent)."""
        return self.parent_span_id is None
    
    @property
    def is_error(self) -> bool:
        """Check if span has error status."""
        return self.status == SpanStatus.ERROR
    
    @property
    def service_name(self) -> str:
        """Get service name from resource."""
        return self.resource.get("service_name", self.resource.get("service.name", "unknown"))
    
    @property
    def operation_name(self) -> str:
        """Get operation name."""
        return self.name
    
    @property
    def http_method(self) -> Optional[str]:
        """Get HTTP method if applicable."""
        return self.attributes.get("http.method") or self.attributes.get("http.request.method")
    
    @property
    def http_url(self) -> Optional[str]:
        """Get HTTP URL if applicable."""
        return self.attributes.get("http.url") or self.attributes.get("url.full")
    
    @property
    def http_status_code(self) -> Optional[int]:
        """Get HTTP status code if applicable."""
        code = self.attributes.get("http.status_code") or self.attributes.get("http.response.status_code")
        return int(code) if code is not None else None
    
    @property
    def db_system(self) -> Optional[str]:
        """Get database system if applicable."""
        return self.attributes.get("db.system")
    
    @property
    def db_statement(self) -> Optional[str]:
        """Get database statement if applicable."""
        return self.attributes.get("db.statement")
    
    @property
    def rpc_service(self) -> Optional[str]:
        """Get RPC service name if applicable."""
        return self.attributes.get("rpc.service")
    
    @property
    def rpc_method(self) -> Optional[str]:
        """Get RPC method if applicable."""
        return self.attributes.get("rpc.method")
    
    @property
    def messaging_system(self) -> Optional[str]:
        """Get messaging system if applicable."""
        return self.attributes.get("messaging.system")
    
    @property
    def messaging_destination(self) -> Optional[str]:
        """Get messaging destination if applicable."""
        return self.attributes.get("messaging.destination.name") or self.attributes.get("messaging.destination")
    
    def get_attribute(self, key: str, default: Any = None) -> Any:
        """Get attribute value by key."""
        return self.attributes.get(key, default)
    
    def has_error_event(self) -> bool:
        """Check if span has an error/exception event."""
        for event in self.events:
            name = event.get("name", "").lower()
            if "error" in name or "exception" in name:
                return True
        return False
    
    def get_events(self) -> list[SpanEvent]:
        """Get events as SpanEvent objects."""
        result = []
        for event in self.events:
            ts = event.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            elif not isinstance(ts, datetime):
                ts = self.start_time
            
            result.append(SpanEvent(
                name=event.get("name", ""),
                timestamp=ts,
                attributes=event.get("attributes", {}),
            ))
        return result
    
    def get_links(self) -> list[SpanLink]:
        """Get links as SpanLink objects."""
        return [
            SpanLink(
                trace_id=link.get("trace_id", ""),
                span_id=link.get("span_id", ""),
                attributes=link.get("attributes", {}),
            )
            for link in self.links
        ]
    
    def to_context(self) -> TraceContext:
        """Get trace context for this span."""
        return TraceContext(
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "status_message": self.status_message,
            "attributes": self.attributes,
            "events": self.events,
            "links": self.links,
            "resource": self.resource,
            "service_name": self.service_name,
        }
    
    @classmethod
    def from_jaeger(cls, data: dict[str, Any]) -> "Span":
        """Create Span from Jaeger format."""
        # Jaeger timestamps are in microseconds
        start_time = datetime.fromtimestamp(
            data.get("startTime", 0) / 1_000_000,
            tz=timezone.utc,
        )
        duration_us = data.get("duration", 0)
        end_time = start_time + timedelta(microseconds=duration_us)
        
        # Parse tags to attributes
        attributes = {}
        for tag in data.get("tags", []):
            attributes[tag["key"]] = tag.get("value")
        
        # Parse logs to events
        events = []
        for log in data.get("logs", []):
            event_attrs = {}
            event_name = "log"
            for field in log.get("fields", []):
                if field["key"] == "event":
                    event_name = field["value"]
                else:
                    event_attrs[field["key"]] = field.get("value")
            
            events.append({
                "name": event_name,
                "timestamp": datetime.fromtimestamp(
                    log.get("timestamp", 0) / 1_000_000,
                    tz=timezone.utc,
                ).isoformat(),
                "attributes": event_attrs,
            })
        
        # Determine status
        status = SpanStatus.UNSET
        error = attributes.get("error")
        if error is True or str(error).lower() == "true":
            status = SpanStatus.ERROR
        elif attributes.get("otel.status_code") == "OK":
            status = SpanStatus.OK
        elif attributes.get("otel.status_code") == "ERROR":
            status = SpanStatus.ERROR
        
        # Parse references for parent
        parent_span_id = None
        for ref in data.get("references", []):
            if ref.get("refType") == "CHILD_OF":
                parent_span_id = ref.get("spanID")
                break
        
        # Service name from process
        process = data.get("process", {})
        service_name = process.get("serviceName", "unknown")
        
        return cls(
            trace_id=data.get("traceID", ""),
            span_id=data.get("spanID", ""),
            parent_span_id=parent_span_id,
            name=data.get("operationName", "unknown"),
            kind=cls._parse_span_kind(attributes.get("span.kind")),
            start_time=start_time,
            end_time=end_time,
            status=status,
            status_message=attributes.get("otel.status_description", ""),
            attributes=attributes,
            events=events,
            links=[],
            resource={"service_name": service_name, **{t["key"]: t.get("value") for t in process.get("tags", [])}},
        )
    
    @classmethod
    def from_otlp(cls, data: dict[str, Any], resource: dict[str, Any] = None) -> "Span":
        """Create Span from OTLP format."""
        # OTLP timestamps are in nanoseconds
        start_ns = data.get("startTimeUnixNano", 0)
        end_ns = data.get("endTimeUnixNano", 0)
        
        start_time = datetime.fromtimestamp(start_ns / 1e9, tz=timezone.utc)
        end_time = datetime.fromtimestamp(end_ns / 1e9, tz=timezone.utc)
        
        # Parse attributes
        attributes = cls._parse_otlp_attributes(data.get("attributes", []))
        
        # Parse events
        events = []
        for event in data.get("events", []):
            events.append({
                "name": event.get("name", ""),
                "timestamp": datetime.fromtimestamp(
                    event.get("timeUnixNano", 0) / 1e9,
                    tz=timezone.utc,
                ).isoformat(),
                "attributes": cls._parse_otlp_attributes(event.get("attributes", [])),
            })
        
        # Parse links
        links = []
        for link in data.get("links", []):
            links.append({
                "trace_id": link.get("traceId", ""),
                "span_id": link.get("spanId", ""),
                "attributes": cls._parse_otlp_attributes(link.get("attributes", [])),
            })
        
        # Status
        status_data = data.get("status", {})
        status_code = status_data.get("code", 0)
        if status_code == 1:
            status = SpanStatus.OK
        elif status_code == 2:
            status = SpanStatus.ERROR
        else:
            status = SpanStatus.UNSET
        
        # Kind mapping
        kind_map = {
            0: SpanKind.UNSPECIFIED,
            1: SpanKind.INTERNAL,
            2: SpanKind.SERVER,
            3: SpanKind.CLIENT,
            4: SpanKind.PRODUCER,
            5: SpanKind.CONSUMER,
        }
        kind = kind_map.get(data.get("kind", 0), SpanKind.UNSPECIFIED)
        
        return cls(
            trace_id=data.get("traceId", ""),
            span_id=data.get("spanId", ""),
            parent_span_id=data.get("parentSpanId") or None,
            name=data.get("name", "unknown"),
            kind=kind,
            start_time=start_time,
            end_time=end_time,
            status=status,
            status_message=status_data.get("message", ""),
            attributes=attributes,
            events=events,
            links=links,
            resource=resource or {},
        )
    
    @classmethod
    def from_zipkin(cls, data: dict[str, Any]) -> "Span":
        """Create Span from Zipkin format."""
        # Zipkin timestamps are in microseconds
        start_us = data.get("timestamp", 0)
        duration_us = data.get("duration", 0)
        
        start_time = datetime.fromtimestamp(start_us / 1e6, tz=timezone.utc)
        end_time = start_time + timedelta(microseconds=duration_us)
        
        # Tags to attributes
        attributes = dict(data.get("tags", {}))
        
        # Annotations to events
        events = []
        for annotation in data.get("annotations", []):
            events.append({
                "name": annotation.get("value", ""),
                "timestamp": datetime.fromtimestamp(
                    annotation.get("timestamp", 0) / 1e6,
                    tz=timezone.utc,
                ).isoformat(),
                "attributes": {},
            })
        
        # Status from tags
        status = SpanStatus.UNSET
        if attributes.get("error"):
            status = SpanStatus.ERROR
        
        # Kind from kind field
        kind_str = data.get("kind", "").upper()
        kind_map = {
            "CLIENT": SpanKind.CLIENT,
            "SERVER": SpanKind.SERVER,
            "PRODUCER": SpanKind.PRODUCER,
            "CONSUMER": SpanKind.CONSUMER,
        }
        kind = kind_map.get(kind_str, SpanKind.INTERNAL)
        
        # Service from localEndpoint
        local_endpoint = data.get("localEndpoint", {})
        service_name = local_endpoint.get("serviceName", "unknown")
        
        return cls(
            trace_id=data.get("traceId", ""),
            span_id=data.get("id", ""),
            parent_span_id=data.get("parentId"),
            name=data.get("name", "unknown"),
            kind=kind,
            start_time=start_time,
            end_time=end_time,
            status=status,
            attributes=attributes,
            events=events,
            links=[],
            resource={"service_name": service_name},
        )
    
    @staticmethod
    def _parse_span_kind(value: Optional[str]) -> SpanKind:
        """Parse span kind from string."""
        if not value:
            return SpanKind.INTERNAL
        
        value = value.lower()
        kind_map = {
            "server": SpanKind.SERVER,
            "client": SpanKind.CLIENT,
            "producer": SpanKind.PRODUCER,
            "consumer": SpanKind.CONSUMER,
            "internal": SpanKind.INTERNAL,
        }
        return kind_map.get(value, SpanKind.INTERNAL)
    
    @staticmethod
    def _parse_otlp_attributes(attrs: list[dict]) -> dict[str, Any]:
        """Parse OTLP attributes to dict."""
        result = {}
        for attr in attrs:
            key = attr.get("key", "")
            value = attr.get("value", {})
            
            # OTLP values are typed
            if "stringValue" in value:
                result[key] = value["stringValue"]
            elif "intValue" in value:
                result[key] = int(value["intValue"])
            elif "doubleValue" in value:
                result[key] = float(value["doubleValue"])
            elif "boolValue" in value:
                result[key] = value["boolValue"]
            elif "arrayValue" in value:
                result[key] = [v.get("stringValue", v) for v in value["arrayValue"].get("values", [])]
            else:
                result[key] = value
        
        return result


class Trace(BaseModel):
    """
    A complete distributed trace.
    
    A trace is a collection of spans that share the same trace ID,
    representing a single request's journey through the system.
    """
    
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    trace_id: str = Field(..., description="Unique trace identifier")
    spans: list[Span] = Field(default_factory=list)
    
    @property
    def root_span(self) -> Optional[Span]:
        """Get the root span of the trace."""
        for span in self.spans:
            if span.is_root:
                return span
        # If no explicit root, return the earliest span
        if self.spans:
            return min(self.spans, key=lambda s: s.start_time)
        return None
    
    @property
    def span_count(self) -> int:
        """Get number of spans in trace."""
        return len(self.spans)
    
    @property
    def duration_ms(self) -> float:
        """Get total trace duration in milliseconds."""
        root = self.root_span
        if root:
            return root.duration_ms
        if self.spans:
            start = min(s.start_time for s in self.spans)
            end = max(s.end_time for s in self.spans)
            return (end - start).total_seconds() * 1000
        return 0.0
    
    @property
    def duration(self) -> timedelta:
        """Get total trace duration."""
        return timedelta(milliseconds=self.duration_ms)
    
    @property
    def start_time(self) -> Optional[datetime]:
        """Get trace start time."""
        root = self.root_span
        if root:
            return root.start_time
        if self.spans:
            return min(s.start_time for s in self.spans)
        return None
    
    @property
    def end_time(self) -> Optional[datetime]:
        """Get trace end time."""
        root = self.root_span
        if root:
            return root.end_time
        if self.spans:
            return max(s.end_time for s in self.spans)
        return None
    
    @property
    def services(self) -> set[str]:
        """Get unique services in trace."""
        return {s.service_name for s in self.spans}
    
    @property
    def has_errors(self) -> bool:
        """Check if any span has errors."""
        return any(s.is_error for s in self.spans)
    
    @property
    def error_count(self) -> int:
        """Get number of error spans."""
        return sum(1 for s in self.spans if s.is_error)
    
    @property
    def depth(self) -> int:
        """Get maximum span depth in trace."""
        if not self.spans:
            return 0
        
        # Build parent-child map
        children: dict[str, list[str]] = {}
        for span in self.spans:
            if span.parent_span_id:
                if span.parent_span_id not in children:
                    children[span.parent_span_id] = []
                children[span.parent_span_id].append(span.span_id)
        
        # Find max depth from root
        def get_depth(span_id: str) -> int:
            if span_id not in children:
                return 1
            return 1 + max(get_depth(child) for child in children[span_id])
        
        root = self.root_span
        if root:
            return get_depth(root.span_id)
        return 1
    
    def get_span(self, span_id: str) -> Optional[Span]:
        """Get a span by ID."""
        for span in self.spans:
            if span.span_id == span_id:
                return span
        return None
    
    def get_children(self, span_id: str) -> list[Span]:
        """Get child spans of a given span."""
        return [s for s in self.spans if s.parent_span_id == span_id]
    
    def get_ancestors(self, span_id: str) -> list[Span]:
        """Get all ancestor spans of a given span."""
        ancestors = []
        span = self.get_span(span_id)
        
        while span and span.parent_span_id:
            parent = self.get_span(span.parent_span_id)
            if parent:
                ancestors.append(parent)
                span = parent
            else:
                break
        
        return ancestors
    
    def get_critical_path(self) -> list[Span]:
        """
        Get the critical path (longest path) through the trace.
        
        The critical path is the sequence of spans that determines
        the total trace duration.
        """
        if not self.spans:
            return []
        
        # Build span lookup and children map
        span_map = {s.span_id: s for s in self.spans}
        children: dict[str, list[str]] = {}
        
        for span in self.spans:
            if span.parent_span_id and span.parent_span_id in span_map:
                if span.parent_span_id not in children:
                    children[span.parent_span_id] = []
                children[span.parent_span_id].append(span.span_id)
        
        # Find critical path recursively
        def find_path(span_id: str) -> tuple[float, list[str]]:
            span = span_map[span_id]
            
            if span_id not in children:
                return span.duration_ms, [span_id]
            
            # Find the child path with longest duration
            max_duration = 0.0
            max_path: list[str] = []
            
            for child_id in children[span_id]:
                child_duration, child_path = find_path(child_id)
                if child_duration > max_duration:
                    max_duration = child_duration
                    max_path = child_path
            
            return span.duration_ms + max_duration, [span_id] + max_path
        
        root = self.root_span
        if not root:
            return []
        
        _, path = find_path(root.span_id)
        return [span_map[sid] for sid in path if sid in span_map]
    
    def get_spans_by_service(self, service: str) -> list[Span]:
        """Get all spans for a specific service."""
        return [s for s in self.spans if s.service_name == service]
    
    def get_spans_by_operation(self, operation: str) -> list[Span]:
        """Get all spans for a specific operation."""
        return [s for s in self.spans if s.name == operation]
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trace_id": self.trace_id,
            "spans": [s.to_dict() for s in self.spans],
            "span_count": self.span_count,
            "duration_ms": self.duration_ms,
            "services": list(self.services),
            "has_errors": self.has_errors,
            "error_count": self.error_count,
            "depth": self.depth,
        }
    
    @classmethod
    def from_spans(cls, spans: list[Span]) -> "Trace":
        """Create a Trace from a list of spans."""
        if not spans:
            raise ValueError("Cannot create trace from empty span list")
        
        trace_id = spans[0].trace_id
        if not all(s.trace_id == trace_id for s in spans):
            raise ValueError("All spans must have the same trace_id")
        
        return cls(trace_id=trace_id, spans=spans)
    
    def add_span(self, span: Span) -> None:
        """Add a span to the trace."""
        if span.trace_id != self.trace_id:
            raise ValueError(f"Span trace_id {span.trace_id} doesn't match trace {self.trace_id}")
        self.spans.append(span)
    
    def validate_structure(self) -> list[str]:
        """
        Validate trace structure and return any issues.
        
        Checks for:
        - Missing parent spans
        - Timing inconsistencies
        - Multiple roots
        """
        issues = []
        span_ids = {s.span_id for s in self.spans}
        
        roots = [s for s in self.spans if s.is_root]
        if len(roots) > 1:
            issues.append(f"Multiple root spans found: {len(roots)}")
        elif len(roots) == 0:
            issues.append("No root span found")
        
        for span in self.spans:
            # Check for missing parents
            if span.parent_span_id and span.parent_span_id not in span_ids:
                issues.append(f"Span {span.span_id} references missing parent {span.parent_span_id}")
            
            # Check timing
            if span.end_time < span.start_time:
                issues.append(f"Span {span.span_id} has negative duration")
            
            # Check child timing vs parent
            if span.parent_span_id and span.parent_span_id in span_ids:
                parent = next(s for s in self.spans if s.span_id == span.parent_span_id)
                if span.start_time < parent.start_time:
                    issues.append(f"Span {span.span_id} starts before parent")
        
        return issues
