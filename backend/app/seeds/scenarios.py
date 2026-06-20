"""The four canned failing-service scenarios.

Each function returns a fully-formed `ScenarioBundle`. They are intentionally
hand-authored (not randomized) so the demo is reproducible and the eval harness
has stable ground truth. Every scenario plants a real culprit plus a few
distractors (slow-but-innocent spans, noisy warnings) so retrieval has to work.
"""

from __future__ import annotations

from ..models import (
    Incident,
    LogLevel,
    RootCause,
    ScenarioBundle,
    Status,
)
from .builder import TraceBuilder


def slow_db_query() -> ScenarioBundle:
    """Checkout latency spike caused by an unindexed SELECT ... FOR UPDATE that
    sits behind a row lock. No errors — just a degraded span hiding in a slow trace."""
    key = "slow-db-query"
    b = TraceBuilder("trc-checkout-01", "api-gateway", t0_ms=0)

    root = b.span("POST /checkout", "api-gateway", 0, 842, Status.DEGRADED)
    b.span("validate-cart", "cart-svc", 6, 18, Status.OK, parent=root)
    b.span("charge-payment", "payment-svc", 28, 92, Status.OK, parent=root)
    persist = b.span("persist-order", "order-svc", 124, 706, Status.DEGRADED, parent=root)
    b.span(
        "db.query INSERT orders", "order-svc", 130, 36, Status.OK, parent=persist,
        attributes={"db.system": "postgres", "db.table": "orders"},
    )
    culprit = b.span(
        "db.query SELECT inventory FOR UPDATE", "order-svc", 172, 628, Status.DEGRADED,
        parent=persist,
        attributes={
            "db.system": "postgres",
            "db.table": "inventory",
            "db.rows_examined": "1840221",
            "db.index": "none",
        },
    )

    b.log(176, LogLevel.WARN, "slow query: SELECT ... FROM inventory FOR UPDATE took 624ms", culprit,
          {"db.lock_wait_ms": "402"})
    cl = b.log(178, LogLevel.WARN, "lock wait detected on inventory row (sku=SKU-9912), 402ms", culprit)
    b.log(802, LogLevel.INFO, "checkout completed (degraded latency 842ms, p99 budget 300ms)", root)
    # Distractors: an innocent retry and a routine info line.
    b.log(34, LogLevel.INFO, "payment authorized via stripe (pi_3Nx...)", None)

    incident = Incident(
        id="inc-slow-db", title="Checkout latency breaching p99 SLO", scenario_key=key,
        trace_ids=[b.trace_id],
        summary="Checkout requests degraded to ~840ms (p99 budget 300ms). Errors flat; latency only.",
        window_start=b.trace().start, window_end=b.trace().end,
    )
    return ScenarioBundle(
        scenario_key=key, title="Slow DB query",
        description="Unindexed, lock-contended SELECT FOR UPDATE on inventory blows the checkout latency budget.",
        incident=incident, traces=[b.trace()], spans=b.spans, logs=b.logs,
        root_cause=RootCause(
            scenario_key=key,
            summary="An unindexed `SELECT ... FROM inventory FOR UPDATE` in order-svc scans ~1.8M rows and waits on a row lock, adding ~620ms to every checkout.",
            culprit_service="order-svc",
            keywords=["inventory", "select", "for update", "lock", "index", "slow query", "order-svc"],
            evidence_span_ids=[culprit, persist],
            evidence_log_ids=[cl],
        ),
    )


def cascading_timeout() -> ScenarioBundle:
    """A cache outage makes profile-svc slow; recommendations-svc hits its client
    timeout and the gateway returns 504. Classic upstream cascade."""
    key = "cascading-timeout"
    b = TraceBuilder("trc-feed-01", "api-gateway", t0_ms=0)

    root = b.span("GET /feed", "api-gateway", 0, 1012, Status.ERROR)
    b.span("auth-check", "auth-svc", 4, 12, Status.OK, parent=root)
    recs = b.span("get-recommendations", "recommendations-svc", 20, 988, Status.ERROR, parent=root,
                  attributes={"rpc.timeout_ms": "1000", "rpc.deadline_exceeded": "true"})
    profile = b.span("get-profile", "profile-svc", 30, 970, Status.DEGRADED, parent=recs)
    cache = b.span("cache.get profile:*", "profile-svc", 34, 8, Status.ERROR, parent=profile,
                   attributes={"cache.system": "redis", "cache.result": "connection_refused"})
    b.span("db.query SELECT profiles", "profile-svc", 46, 918, Status.DEGRADED, parent=profile,
           attributes={"db.system": "postgres", "db.note": "cache bypass — every read hitting primary"})

    b.log(36, LogLevel.ERROR, "redis: connection refused (profile-cache:6379) — falling back to db", cache,
          {"cache.host": "profile-cache:6379"})
    rootlog = b.log(40, LogLevel.WARN, "cache miss storm: 100% of profile reads bypassing redis to postgres", profile)
    b.log(1008, LogLevel.ERROR, "deadline exceeded calling profile-svc (1000ms) — aborting recommendations", recs)
    b.log(1010, LogLevel.ERROR, "GET /feed -> 504 Gateway Timeout", root)

    incident = Incident(
        id="inc-cascade", title="Feed endpoint returning 504s", scenario_key=key,
        trace_ids=[b.trace_id],
        summary="GET /feed failing with 504. Recommendations-svc timing out on profile-svc.",
        window_start=b.trace().start, window_end=b.trace().end,
    )
    return ScenarioBundle(
        scenario_key=key, title="Cascading timeout",
        description="Redis outage forces profile-svc to bypass cache; downstream slowness cascades into recommendations timeouts and gateway 504s.",
        incident=incident, traces=[b.trace()], spans=b.spans, logs=b.logs,
        root_cause=RootCause(
            scenario_key=key,
            summary="profile-cache (redis) is down (connection refused). Every profile read bypasses cache to postgres, pushing profile-svc latency past recommendations-svc's 1000ms deadline, cascading into gateway 504s.",
            culprit_service="profile-svc",
            keywords=["redis", "cache", "connection refused", "timeout", "deadline", "profile-svc", "cascade", "504"],
            evidence_span_ids=[cache, profile, recs],
            evidence_log_ids=[rootlog],
        ),
    )


def bad_deploy() -> ScenarioBundle:
    """Error rate on pricing endpoint spikes immediately after order-svc v2.4.0
    ships — a null deref in a new discount code path."""
    key = "bad-deploy"
    b = TraceBuilder("trc-price-01", "api-gateway", t0_ms=0)

    root = b.span("POST /cart/price", "api-gateway", 0, 64, Status.ERROR)
    b.span("load-cart", "cart-svc", 4, 14, Status.OK, parent=root)
    price = b.span("compute-price", "order-svc", 22, 38, Status.ERROR, parent=root,
                   attributes={"deploy.version": "2.4.0", "deploy.age_min": "7"})
    culprit = b.span("apply-discount", "order-svc", 30, 6, Status.ERROR, parent=price,
                     attributes={"deploy.version": "2.4.0", "code.path": "DiscountEngine.apply"})

    el = b.log(33, LogLevel.ERROR,
               "NullPointerException: Cannot read 'rate' of null at DiscountEngine.apply (pricing.kt:142)", culprit,
               {"deploy.version": "2.4.0", "exception.type": "NullPointerException"})
    b.log(34, LogLevel.ERROR, "compute-price failed for cart c-8821 — returning 500", price,
          {"deploy.version": "2.4.0"})
    b.log(1, LogLevel.INFO, "order-svc v2.4.0 rolled out to 100% (was v2.3.7) 7m ago", None,
          {"deploy.version": "2.4.0", "deploy.previous": "2.3.7"})
    dl = b.log(2, LogLevel.WARN, "error rate on /cart/price jumped 0.1% -> 38% at deploy boundary", None,
               {"deploy.version": "2.4.0"})

    incident = Incident(
        id="inc-bad-deploy", title="Pricing 500s spiking after deploy", scenario_key=key,
        trace_ids=[b.trace_id],
        summary="/cart/price error rate jumped to ~38% coinciding with order-svc v2.4.0.",
        window_start=b.trace().start, window_end=b.trace().end,
    )
    return ScenarioBundle(
        scenario_key=key, title="Bad deploy",
        description="order-svc v2.4.0 introduces a null deref in the new discount code path; error rate spikes at the deploy boundary.",
        incident=incident, traces=[b.trace()], spans=b.spans, logs=b.logs,
        root_cause=RootCause(
            scenario_key=key,
            summary="order-svc v2.4.0 introduced a NullPointerException in DiscountEngine.apply (new discount path) — error rate on /cart/price spikes from 0.1% to 38% exactly at the deploy boundary. Roll back to v2.3.7.",
            culprit_service="order-svc",
            keywords=["deploy", "v2.4.0", "2.4.0", "nullpointer", "discount", "rollback", "regression", "order-svc"],
            evidence_span_ids=[culprit, price],
            evidence_log_ids=[el, dl],
        ),
    )


def noisy_neighbor() -> ScenarioBundle:
    """A nightly analytics batch saturates the shared DB connection pool; an
    unrelated api-svc endpoint slows down waiting for a connection — no fault in
    its own code."""
    key = "noisy-neighbor"
    b = TraceBuilder("trc-orders-list-01", "api-gateway", t0_ms=0)

    root = b.span("GET /orders", "api-gateway", 0, 588, Status.DEGRADED)
    b.span("auth-check", "auth-svc", 4, 11, Status.OK, parent=root)
    handler = b.span("list-orders", "api-svc", 18, 560, Status.DEGRADED, parent=root)
    pool = b.span("db.pool.acquire", "api-svc", 22, 506, Status.DEGRADED, parent=handler,
                  attributes={"db.pool.size": "20", "db.pool.in_use": "20", "db.pool.wait_ms": "498"})
    b.span("db.query SELECT orders", "api-svc", 530, 44, Status.OK, parent=handler,
           attributes={"db.system": "postgres", "db.duration_ms": "44"})

    pl = b.log(24, LogLevel.WARN, "waited 498ms for connection from pool (20/20 in use)", pool,
               {"db.pool.exhausted": "true"})
    nl = b.log(25, LogLevel.WARN,
               "connection pool dominated by client=analytics-batch (17/20 connections, job=nightly_rollup)",
               pool, {"db.client": "analytics-batch", "job": "nightly_rollup"})
    b.log(528, LogLevel.INFO, "acquired connection after 498ms; query itself fast (44ms)", handler)
    b.log(0, LogLevel.INFO, "analytics-batch nightly_rollup started — scanning 14 tables", None,
          {"job": "nightly_rollup", "client": "analytics-batch"})

    incident = Incident(
        id="inc-noisy", title="/orders latency up, query times normal", scenario_key=key,
        trace_ids=[b.trace_id],
        summary="GET /orders degraded to ~590ms but the SQL itself is fast (44ms). Time is spent waiting for a DB connection.",
        window_start=b.trace().start, window_end=b.trace().end,
    )
    return ScenarioBundle(
        scenario_key=key, title="Noisy neighbor",
        description="A nightly analytics batch holds 17/20 shared DB connections; api-svc stalls ~500ms acquiring a connection despite fast queries.",
        incident=incident, traces=[b.trace()], spans=b.spans, logs=b.logs,
        root_cause=RootCause(
            scenario_key=key,
            summary="The `analytics-batch` nightly_rollup job is holding 17 of 20 shared postgres connections, exhausting the pool. api-svc spends ~500ms waiting to acquire a connection even though its own query runs in 44ms. Isolate analytics onto its own pool/replica.",
            culprit_service="analytics-batch",
            keywords=["connection pool", "pool", "exhausted", "analytics", "batch", "noisy neighbor", "wait", "contention"],
            evidence_span_ids=[pool, handler],
            evidence_log_ids=[pl, nl],
        ),
    )
