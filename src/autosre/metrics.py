"""
Prometheus Metrics Exporter for OpenSRE

Provides comprehensive observability for OpenSRE itself, including:
- Investigation metrics (count, duration, confidence)
- Action metrics (suggested, approved, executed)
- LLM metrics (requests, latency, tokens)
- Adapter health metrics
"""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# =============================================================================
# Investigation Metrics
# =============================================================================

INVESTIGATIONS_TOTAL = Counter(
    'opensre_investigations_total',
    'Total number of investigations',
    ['namespace', 'status']  # status: completed, failed, timeout
)

INVESTIGATION_DURATION = Histogram(
    'opensre_investigation_duration_seconds',
    'Investigation duration in seconds',
    ['namespace'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)

INVESTIGATION_CONFIDENCE = Histogram(
    'opensre_investigation_confidence',
    'Investigation confidence scores',
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

INVESTIGATION_ITERATIONS = Histogram(
    'opensre_investigation_iterations',
    'Number of iterations per investigation',
    buckets=[1, 2, 3, 4, 5]
)

ACTIVE_INVESTIGATIONS = Gauge(
    'opensre_active_investigations',
    'Currently running investigations'
)

# =============================================================================
# Action Metrics
# =============================================================================

ACTIONS_TOTAL = Counter(
    'opensre_actions_total',
    'Total actions suggested',
    ['risk', 'status']  # status: suggested, approved, rejected, executed
)

ACTIONS_APPROVED = Counter(
    'opensre_actions_approved_total',
    'Actions approved by humans',
    ['risk']
)

ACTIONS_REJECTED = Counter(
    'opensre_actions_rejected_total',
    'Actions rejected by humans',
    ['risk']
)

ACTIONS_EXECUTED = Counter(
    'opensre_actions_executed_total',
    'Actions executed',
    ['risk', 'result']  # result: success, failure
)

ACTION_EXECUTION_DURATION = Histogram(
    'opensre_action_execution_duration_seconds',
    'Action execution duration in seconds',
    ['risk'],
    buckets=[0.5, 1, 2, 5, 10, 30, 60]
)

# =============================================================================
# LLM Metrics
# =============================================================================

LLM_REQUESTS = Counter(
    'opensre_llm_requests_total',
    'LLM API requests',
    ['provider', 'model', 'status']  # status: success, error
)

LLM_LATENCY = Histogram(
    'opensre_llm_latency_seconds',
    'LLM request latency',
    ['provider', 'model'],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120]
)

LLM_TOKENS = Counter(
    'opensre_llm_tokens_total',
    'LLM tokens used',
    ['provider', 'model', 'direction']  # direction: input, output, total
)

LLM_ERRORS = Counter(
    'opensre_llm_errors_total',
    'LLM request errors',
    ['provider', 'model', 'error_type']
)

# =============================================================================
# Adapter Health Metrics
# =============================================================================

ADAPTER_HEALTH = Gauge(
    'opensre_adapter_health',
    'Adapter connection health (1=healthy, 0=unhealthy)',
    ['adapter']  # prometheus, kubernetes, slack, llm
)

ADAPTER_LATENCY = Histogram(
    'opensre_adapter_latency_seconds',
    'Adapter health check latency',
    ['adapter'],
    buckets=[0.1, 0.25, 0.5, 1, 2, 5]
)

ADAPTER_ERRORS = Counter(
    'opensre_adapter_errors_total',
    'Adapter errors',
    ['adapter', 'error_type']
)

# =============================================================================
# Observation Metrics
# =============================================================================

OBSERVATIONS_COLLECTED = Counter(
    'opensre_observations_collected_total',
    'Total observations collected',
    ['source', 'type']  # source: prometheus, kubernetes; type: metric, event, log
)

OBSERVATION_DURATION = Histogram(
    'opensre_observation_duration_seconds',
    'Time to collect observations',
    ['source'],
    buckets=[0.5, 1, 2, 5, 10, 30]
)

# =============================================================================
# API Metrics
# =============================================================================

API_REQUESTS = Counter(
    'opensre_api_requests_total',
    'API requests',
    ['method', 'endpoint', 'status_code']
)

API_LATENCY = Histogram(
    'opensre_api_latency_seconds',
    'API request latency',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5]
)

WEBSOCKET_CONNECTIONS = Gauge(
    'opensre_websocket_connections',
    'Active WebSocket connections'
)

# =============================================================================
# System Metrics
# =============================================================================

INFO = Gauge(
    'opensre_info',
    'OpenSRE version and configuration info',
    ['version', 'llm_provider']
)


# =============================================================================
# Helper Functions
# =============================================================================

def get_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    return generate_latest()


def get_content_type() -> str:
    """Get the content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST


def record_investigation_start():
    """Record the start of an investigation."""
    ACTIVE_INVESTIGATIONS.inc()


def record_investigation_end(
    namespace: str,
    status: str,
    duration: float,
    confidence: float,
    iterations: int
):
    """Record the completion of an investigation."""
    ACTIVE_INVESTIGATIONS.dec()
    INVESTIGATIONS_TOTAL.labels(namespace=namespace, status=status).inc()
    INVESTIGATION_DURATION.labels(namespace=namespace).observe(duration)
    INVESTIGATION_CONFIDENCE.observe(confidence)
    INVESTIGATION_ITERATIONS.observe(iterations)


def record_action_suggested(risk: str):
    """Record a suggested action."""
    ACTIONS_TOTAL.labels(risk=risk, status='suggested').inc()


def record_action_approved(risk: str):
    """Record an approved action."""
    ACTIONS_APPROVED.labels(risk=risk).inc()
    ACTIONS_TOTAL.labels(risk=risk, status='approved').inc()


def record_action_rejected(risk: str):
    """Record a rejected action."""
    ACTIONS_REJECTED.labels(risk=risk).inc()
    ACTIONS_TOTAL.labels(risk=risk, status='rejected').inc()


def record_action_executed(risk: str, success: bool, duration: float):
    """Record an executed action."""
    result = 'success' if success else 'failure'
    ACTIONS_EXECUTED.labels(risk=risk, result=result).inc()
    ACTIONS_TOTAL.labels(risk=risk, status='executed').inc()
    ACTION_EXECUTION_DURATION.labels(risk=risk).observe(duration)


def record_llm_request(
    provider: str,
    model: str,
    success: bool,
    latency: float,
    tokens: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
):
    """Record an LLM request."""
    status = 'success' if success else 'error'
    LLM_REQUESTS.labels(provider=provider, model=model, status=status).inc()
    LLM_LATENCY.labels(provider=provider, model=model).observe(latency)

    # Record tokens (support both total and separate input/output)
    if input_tokens is not None:
        LLM_TOKENS.labels(provider=provider, model=model, direction='input').inc(input_tokens)
    if output_tokens is not None:
        LLM_TOKENS.labels(provider=provider, model=model, direction='output').inc(output_tokens)
    if tokens is not None:
        LLM_TOKENS.labels(provider=provider, model=model, direction='total').inc(tokens)


def record_llm_error(provider: str, model: str, error_type: str):
    """Record an LLM error."""
    LLM_ERRORS.labels(provider=provider, model=model, error_type=error_type).inc()


def record_adapter_health(adapter: str, healthy: bool, latency: float):
    """Record adapter health check result."""
    ADAPTER_HEALTH.labels(adapter=adapter).set(1 if healthy else 0)
    ADAPTER_LATENCY.labels(adapter=adapter).observe(latency)


def record_adapter_error(adapter: str, error_type: str):
    """Record an adapter error."""
    ADAPTER_ERRORS.labels(adapter=adapter, error_type=error_type).inc()


def record_observation(source: str, observation_type: str, count: int = 1):
    """Record collected observations."""
    OBSERVATIONS_COLLECTED.labels(source=source, type=observation_type).inc(count)


def record_observation_duration(source: str, duration: float):
    """Record observation collection duration."""
    OBSERVATION_DURATION.labels(source=source).observe(duration)


def record_api_request(method: str, endpoint: str, status_code: int, latency: float):
    """Record an API request."""
    API_REQUESTS.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
    API_LATENCY.labels(method=method, endpoint=endpoint).observe(latency)


def set_version_info(version: str, llm_provider: str):
    """Set OpenSRE version info."""
    INFO.labels(version=version, llm_provider=llm_provider).set(1)
