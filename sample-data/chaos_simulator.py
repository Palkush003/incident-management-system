#!/usr/bin/env python3
"""
Chaos Monkey Simulator — generates realistic multi-component failure cascades.

Usage:
  python chaos_simulator.py --scenario rdbms_outage --burst-rate 1000 --duration 30
  python chaos_simulator.py --scenario all --burst-rate 500 --duration 60
"""
import asyncio
import httpx
import json
import random
import argparse
import time
from datetime import datetime


BASE_URL = "http://localhost:8000"

# ── Failure Scenarios ─────────────────────────────────────────────────────────

SCENARIOS = {
    "rdbms_outage": {
        "name": "RDBMS Primary Outage",
        "description": "Primary PostgreSQL fails → cascading API 503s",
        "phases": [
            {
                "delay": 0,
                "signals": [
                    {
                        "component_id": "POSTGRES_PRIMARY",
                        "component_type": "RDBMS",
                        "severity": "P0",
                        "message": "Primary database connection refused — server unreachable",
                        "error_code": "ERR_CONNECTION_REFUSED",
                        "source_host": "app-server-01",
                        "metadata": {"replica_lag_ms": 0, "connections_active": 0}
                    }
                ] * 50
            },
            {
                "delay": 2,
                "signals": [
                    {
                        "component_id": "API_GATEWAY_01",
                        "component_type": "API",
                        "severity": "P1",
                        "message": "HTTP 503 Service Unavailable — upstream DB timeout",
                        "error_code": "HTTP_503",
                        "source_host": "lb-node-01",
                        "metadata": {"upstream": "POSTGRES_PRIMARY", "timeout_ms": 30000}
                    }
                ] * 40
            },
        ]
    },
    "cache_degradation": {
        "name": "Cache Cluster Memory Exhaustion",
        "description": "Redis OOM → 120 signals in 10s → debounce to 1 Work Item",
        "phases": [
            {
                "delay": 0,
                "signals": [
                    {
                        "component_id": f"CACHE_CLUSTER_0{i % 3 + 1}",
                        "component_type": "CACHE",
                        "severity": "P2",
                        "message": f"OOM killer invoked on cache node {i % 3 + 1}",
                        "error_code": "ERR_OOM",
                        "source_host": f"cache-node-{i % 3 + 1}",
                        "metadata": {"memory_used_mb": 3900 + i * 10, "max_memory_mb": 4096}
                    }
                    for i in range(120)
                ]
            }
        ]
    },
    "mcp_cascade": {
        "name": "MCP Host + API Cascade",
        "description": "MCP Host failure triggers cascading P0/P1 storm across services",
        "phases": [
            {
                "delay": 0,
                "signals": [
                    {
                        "component_id": "MCP_HOST_PRIMARY",
                        "component_type": "MCP_HOST",
                        "severity": "P0",
                        "message": f"MCP host unreachable — health check failed attempt {i + 1}",
                        "error_code": "ERR_HEALTH_CHECK_FAILED",
                        "source_host": "orchestrator-01",
                        "metadata": {"consecutive_failures": i + 1}
                    }
                    for i in range(30)
                ]
            },
            {
                "delay": 1,
                "signals": [
                    {
                        "component_id": "API_GATEWAY_01",
                        "component_type": "API",
                        "severity": "P1",
                        "message": f"Gateway unable to reach MCP upstream — request {i + 1} dropped",
                        "error_code": "HTTP_503",
                        "source_host": f"lb-node-{i % 2 + 1}",
                        "metadata": {"upstream": "MCP_HOST_PRIMARY"}
                    }
                    for i in range(40)
                ]
            },
        ]
    },
    "queue_saturation": {
        "name": "Kafka Queue Saturation",
        "description": "Consumer lag exceeds threshold → P1 alerts",
        "phases": [
            {
                "delay": 0,
                "signals": [
                    {
                        "component_id": "KAFKA_CLUSTER_MAIN",
                        "component_type": "ASYNC_QUEUE",
                        "severity": "P1",
                        "message": f"Consumer group lag: {10000 + i * 500} messages behind",
                        "error_code": "ERR_CONSUMER_LAG",
                        "source_host": f"kafka-broker-{i % 3 + 1}",
                        "metadata": {"lag": 10000 + i * 500, "partition": i % 6}
                    }
                    for i in range(80)
                ]
            }
        ]
    }
}


async def send_batch(client: httpx.AsyncClient, signals: list, burst_rate: int) -> int:
    """Send signals in batches. Returns count of sent signals."""
    batch_size = min(100, burst_rate)
    sent = 0
    for i in range(0, len(signals), batch_size):
        batch = signals[i:i + batch_size]
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/signals/batch",
                json=batch,
                timeout=10.0
            )
            if response.status_code == 202:
                sent += len(batch)
            else:
                print(f"  ⚠ Batch rejected: {response.status_code} — {response.text[:100]}")
        except Exception as e:
            print(f"  ✗ Batch failed: {e}")
        await asyncio.sleep(0.1)
    return sent


async def run_scenario(scenario_name: str, burst_rate: int, duration: int) -> None:
    if scenario_name == "all":
        scenarios = list(SCENARIOS.values())
    elif scenario_name in SCENARIOS:
        scenarios = [SCENARIOS[scenario_name]]
    else:
        print(f"Unknown scenario: {scenario_name}. Available: {', '.join(SCENARIOS.keys())}, all")
        return

    print(f"\n{'='*60}")
    print(f"🐒 CHAOS MONKEY SIMULATOR")
    print(f"{'='*60}")
    print(f"Burst Rate  : {burst_rate} signals/batch")
    print(f"Duration    : {duration}s")
    print(f"Target      : {BASE_URL}")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient() as client:
        # Health check first
        try:
            r = await client.get(f"{BASE_URL}/health", timeout=5.0)
            health = r.json()
            print(f"✅ Backend Status: {health['status']}")
            for dep, status in health.get('dependencies', {}).items():
                icon = '✅' if status == 'healthy' else '⚠'
                print(f"   {icon} {dep}: {status}")
            print()
        except Exception as e:
            print(f"✗ Cannot reach backend at {BASE_URL}: {e}")
            print("  Make sure `docker-compose up` is running.")
            return

        start_time = time.time()
        total_sent = 0

        for scenario in scenarios:
            print(f"🎯 Scenario: {scenario['name']}")
            print(f"   {scenario['description']}")
            print()

            for phase in scenario["phases"]:
                if phase["delay"] > 0:
                    print(f"   ⏳ Waiting {phase['delay']}s before next phase...")
                    await asyncio.sleep(phase["delay"])

                signals = phase["signals"]
                print(f"   📡 Sending {len(signals)} signals...")
                sent = await send_batch(client, signals, burst_rate)
                total_sent += sent
                print(f"   ✓ Sent {sent}/{len(signals)} signals")

            print()

        elapsed = time.time() - start_time
        print(f"{'='*60}")
        print(f"✅ Simulation Complete")
        print(f"   Total signals sent : {total_sent}")
        print(f"   Time elapsed       : {elapsed:.1f}s")
        print(f"   Avg throughput     : {total_sent/elapsed:.1f} signals/sec")
        print(f"\n👀 Check the dashboard at http://localhost:3000")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IMS Chaos Monkey Simulator")
    parser.add_argument("--scenario", default="rdbms_outage",
                        choices=list(SCENARIOS.keys()) + ["all"],
                        help="Failure scenario to simulate")
    parser.add_argument("--burst-rate", type=int, default=100,
                        help="Signals per batch (default: 100)")
    parser.add_argument("--duration", type=int, default=30,
                        help="Total duration in seconds (default: 30)")
    parser.add_argument("--url", default="http://localhost:8000",
                        help="Backend URL (default: http://localhost:8000)")
    args = parser.parse_args()
    BASE_URL = args.url

    asyncio.run(run_scenario(args.scenario, args.burst_rate, args.duration))
