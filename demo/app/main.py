"""
Demo application for AutoSRE testing.

A simple HTTP service that:
- Exposes /health, /api/data endpoints
- Has configurable error rate and latency
- Exports Prometheus metrics
- Can be made to fail on demand
"""

import asyncio
import os
import random
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import uvicorn

# Configuration
ERROR_RATE = float(os.getenv("ERROR_RATE", "0.05"))
LATENCY_BASE_MS = int(os.getenv("LATENCY_BASE_MS", "50"))
LATENCY_VARIANCE_MS = int(os.getenv("LATENCY_VARIANCE_MS", "20"))

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Simulated failure modes
failure_modes = {
    "enabled": False,
    "type": None,  # "error_spike", "latency_spike", "oom", "connection_pool"
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 Demo app starting (error_rate={ERROR_RATE}, latency={LATENCY_BASE_MS}ms)")
    yield
    print("Demo app shutting down")


app = FastAPI(title="AutoSRE Demo App", lifespan=lifespan)


async def simulate_latency():
    """Add realistic latency variation."""
    base = LATENCY_BASE_MS / 1000
    variance = LATENCY_VARIANCE_MS / 1000
    
    # Sometimes spike latency if in failure mode
    if failure_modes["enabled"] and failure_modes["type"] == "latency_spike":
        delay = random.uniform(1.0, 5.0)  # 1-5 seconds
    else:
        delay = base + random.uniform(-variance, variance)
    
    await asyncio.sleep(max(0.001, delay))


def should_error() -> bool:
    """Determine if this request should error."""
    if failure_modes["enabled"]:
        if failure_modes["type"] == "error_spike":
            return random.random() < 0.5  # 50% error rate
        elif failure_modes["type"] == "connection_pool":
            return random.random() < 0.8  # 80% errors
    return random.random() < ERROR_RATE


@app.get("/health")
async def health():
    """Health check endpoint."""
    if failure_modes["enabled"] and failure_modes["type"] == "oom":
        raise HTTPException(status_code=503, detail="Service unhealthy - OOM")
    return {"status": "healthy", "timestamp": time.time()}


@app.get("/api/data")
async def get_data():
    """Main API endpoint."""
    start = time.time()
    
    await simulate_latency()
    
    if should_error():
        duration = time.time() - start
        REQUEST_COUNT.labels(method="GET", endpoint="/api/data", status="500").inc()
        REQUEST_LATENCY.labels(method="GET", endpoint="/api/data").observe(duration)
        raise HTTPException(status_code=500, detail="Internal server error")
    
    duration = time.time() - start
    REQUEST_COUNT.labels(method="GET", endpoint="/api/data", status="200").inc()
    REQUEST_LATENCY.labels(method="GET", endpoint="/api/data").observe(duration)
    
    return {
        "data": "Hello from demo app!",
        "timestamp": time.time(),
        "instance_id": os.getenv("HOSTNAME", "local"),
    }


@app.post("/api/data")
async def post_data(payload: dict = None):
    """POST endpoint for testing."""
    start = time.time()
    
    await simulate_latency()
    
    if should_error():
        duration = time.time() - start
        REQUEST_COUNT.labels(method="POST", endpoint="/api/data", status="500").inc()
        REQUEST_LATENCY.labels(method="POST", endpoint="/api/data").observe(duration)
        raise HTTPException(status_code=500, detail="Internal server error")
    
    duration = time.time() - start
    REQUEST_COUNT.labels(method="POST", endpoint="/api/data", status="200").inc()
    REQUEST_LATENCY.labels(method="POST", endpoint="/api/data").observe(duration)
    
    return {"status": "created", "payload": payload}


@app.post("/admin/failure")
async def trigger_failure(failure_type: str = "error_spike", duration_seconds: int = 60):
    """
    Trigger a failure mode for testing AutoSRE.
    
    Types:
    - error_spike: 50% error rate
    - latency_spike: 1-5s latency
    - oom: Service unhealthy
    - connection_pool: 80% connection errors
    """
    failure_modes["enabled"] = True
    failure_modes["type"] = failure_type
    
    async def disable_after():
        await asyncio.sleep(duration_seconds)
        failure_modes["enabled"] = False
        failure_modes["type"] = None
    
    asyncio.create_task(disable_after())
    
    return {
        "status": "failure_mode_enabled",
        "type": failure_type,
        "duration_seconds": duration_seconds,
    }


@app.post("/admin/recover")
async def recover():
    """Disable failure mode."""
    failure_modes["enabled"] = False
    failure_modes["type"] = None
    return {"status": "recovered"}


# Metrics endpoint (separate port in production)
metrics_app = FastAPI()


@metrics_app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import threading
    
    # Run metrics server on port 8081
    def run_metrics():
        uvicorn.run(metrics_app, host="0.0.0.0", port=8081, log_level="warning")
    
    metrics_thread = threading.Thread(target=run_metrics, daemon=True)
    metrics_thread.start()
    
    # Run main app on port 8080
    uvicorn.run(app, host="0.0.0.0", port=8080)
