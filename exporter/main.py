import json
import time
from typing import Any, Dict

import httpx
from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST


OLLAMA_URL = "http://ollama:11434"

app = FastAPI(title="AI Observability Exporter")


REQUEST_COUNT = Counter(
    "ai_requests_total",
    "Total number of AI endpoint requests",
    ["method", "path", "status_class"],
)

ERROR_COUNT = Counter(
    "ai_errors_total",
    "Total number of AI endpoint errors",
    ["method", "path", "status_class"],
)

REQUEST_LATENCY = Histogram(
    "ai_request_duration_seconds",
    "AI endpoint request latency in seconds",
    ["method", "path"],
    buckets=(0.05, 0.1, 0.2, 0.3, 0.5, 1, 1.5, 2, 3, 5, 10, 30, 60, 120),
)

OLLAMA_TOTAL_DURATION = Histogram(
    "ollama_total_duration_seconds",
    "Ollama total_duration reported by the model in seconds",
    ["model"],
    buckets=(0.05, 0.1, 0.2, 0.3, 0.5, 1, 1.5, 2, 3, 5, 10, 30, 60, 120),
)

OLLAMA_TOKENS_PER_SECOND = Gauge(
    "ollama_tokens_per_second",
    "Tokens per second computed from eval_count and eval_duration",
    ["model"],
)

OLLAMA_EVAL_TOKENS = Counter(
    "ollama_eval_tokens_total",
    "Total generated tokens reported by Ollama eval_count",
    ["model"],
)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_to_ollama(path: str, request: Request) -> Response:
    method = request.method
    normalized_path = "/" + path

    body = await request.body()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length", "connection"}
    }

    url = f"{OLLAMA_URL}/{path}"
    start = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            upstream_response = await client.request(
                method=method,
                url=url,
                content=body,
                headers=headers,
                params=request.query_params,
            )

        latency = time.perf_counter() - start
        status_code = upstream_response.status_code
        status_class = f"{status_code // 100}xx"

        REQUEST_COUNT.labels(method, normalized_path, status_class).inc()
        REQUEST_LATENCY.labels(method, normalized_path).observe(latency)

        if status_code >= 400:
            ERROR_COUNT.labels(method, normalized_path, status_class).inc()

        content_type = upstream_response.headers.get("content-type", "")

        if normalized_path == "/api/generate" and "application/json" in content_type:
            collect_ollama_ai_metrics(upstream_response.content)

        return Response(
            content=upstream_response.content,
            status_code=status_code,
            media_type=content_type,
        )

    except Exception as exc:
        latency = time.perf_counter() - start

        REQUEST_COUNT.labels(method, normalized_path, "5xx").inc()
        ERROR_COUNT.labels(method, normalized_path, "5xx").inc()
        REQUEST_LATENCY.labels(method, normalized_path).observe(latency)

        return Response(
            content=json.dumps({"error": str(exc)}),
            status_code=502,
            media_type="application/json",
        )


def collect_ollama_ai_metrics(response_body: bytes) -> None:
    try:
        data: Dict[str, Any] = json.loads(response_body.decode("utf-8"))

        model = data.get("model", "unknown")

        total_duration_ns = data.get("total_duration")
        eval_count = data.get("eval_count")
        eval_duration_ns = data.get("eval_duration")

        if isinstance(total_duration_ns, int) and total_duration_ns > 0:
            OLLAMA_TOTAL_DURATION.labels(model).observe(total_duration_ns / 1_000_000_000)

        if isinstance(eval_count, int) and eval_count > 0:
            OLLAMA_EVAL_TOKENS.labels(model).inc(eval_count)

        if (
            isinstance(eval_count, int)
            and isinstance(eval_duration_ns, int)
            and eval_count > 0
            and eval_duration_ns > 0
        ):
            tokens_per_second = eval_count / (eval_duration_ns / 1_000_000_000)
            OLLAMA_TOKENS_PER_SECOND.labels(model).set(tokens_per_second)

    except Exception:
        pass
