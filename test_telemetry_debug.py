#!/usr/bin/env python3
"""Debug script to test telemetry service data flow."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta, timezone
from ciris_engine.logic.services.graph.telemetry_service import GraphTelemetryService
from ciris_engine.logic.services.graph.memory_service import LocalGraphMemoryService
from ciris_engine.logic.services.lifecycle.time import TimeService
from ciris_engine.logic.buses.memory_bus import MemoryBus
from ciris_engine.logic.registries.base import ServiceRegistry
from ciris_engine.schemas.runtime.enums import Priority, ServiceType


async def test_telemetry_flow():
    print("=== Testing Telemetry Service Data Flow ===\n")
    
    # 1. Create services
    print("1. Creating services...")
    time_service = TimeService()
    memory_service = LocalGraphMemoryService(time_service=time_service)
    service_registry = ServiceRegistry()
    
    # Register memory service
    service_registry.register_service(
        service_type=ServiceType.MEMORY,
        provider=memory_service,
        priority=Priority.HIGH,
        capabilities=["memorize", "recall", "memorize_metric", "recall_timeseries"],
        metadata={}
    )
    
    # Create memory bus
    memory_bus = MemoryBus(service_registry=service_registry, time_service=time_service)
    
    # Create telemetry service
    telemetry_service = GraphTelemetryService(memory_bus=memory_bus, time_service=time_service)
    await telemetry_service.start()
    print("✓ Services created and started\n")
    
    # 2. Test raw recall_timeseries
    print("2. Testing raw recall_timeseries...")
    raw_data = await memory_service.recall_timeseries(
        scope="local",
        hours=1
    )
    print(f"   Found {len(raw_data)} total data points")
    token_metrics = [d for d in raw_data if d.metric_name == "llm.tokens.total"]
    print(f"   Found {len(token_metrics)} token metrics")
    if token_metrics:
        total_tokens = sum(m.value for m in token_metrics)
        print(f"   Total tokens: {total_tokens}")
    print()
    
    # 3. Test query_metrics
    print("3. Testing query_metrics...")
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=1)
    
    metrics = await telemetry_service.query_metrics(
        metric_name="llm.tokens.total",
        start_time=start_time,
        end_time=now
    )
    print(f"   query_metrics returned {len(metrics)} metrics")
    if metrics:
        total_from_query = sum(m['value'] for m in metrics)
        print(f"   Total tokens from query: {total_from_query}")
    print()
    
    # 4. Test get_telemetry_summary
    print("4. Testing get_telemetry_summary...")
    try:
        summary = await telemetry_service.get_telemetry_summary()
        print("   Summary returned:")
        print(f"   - tokens_last_hour: {summary.tokens_last_hour}")
        print(f"   - tokens_24h: {summary.tokens_24h}")
        print(f"   - cost_last_hour_cents: {summary.cost_last_hour_cents}")
        print(f"   - cost_24h_cents: {summary.cost_24h_cents}")
        print(f"   - carbon_last_hour_grams: {summary.carbon_last_hour_grams}")
        print(f"   - carbon_24h_grams: {summary.carbon_24h_grams}")
    except Exception as e:
        print(f"   ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # 5. Debug the actual query logic
    print("5. Debugging query logic...")
    
    # Test what happens in get_telemetry_summary for tokens
    metric_types = [
        ("llm.tokens.total", "tokens"),
        ("llm.cost.cents", "cost"),
        ("llm.environmental.carbon_grams", "carbon"),
    ]
    
    for metric_name, metric_type in metric_types:
        print(f"\n   Testing {metric_name}:")
        
        # Get 24h data
        day_ago = now - timedelta(hours=24)
        day_metrics = await telemetry_service.query_metrics(
            metric_name=metric_name,
            start_time=day_ago,
            end_time=now
        )
        print(f"   - Found {len(day_metrics)} metrics in 24h")
        
        # Get 1h data
        hour_ago = now - timedelta(hours=1)
        hour_metrics = await telemetry_service.query_metrics(
            metric_name=metric_name,
            start_time=hour_ago,
            end_time=now
        )
        print(f"   - Found {len(hour_metrics)} metrics in 1h")
        
        # Sum values
        if day_metrics:
            total_24h = sum(m['value'] for m in day_metrics)
            print(f"   - Total 24h: {total_24h}")
        
        if hour_metrics:
            total_1h = sum(m['value'] for m in hour_metrics)
            print(f"   - Total 1h: {total_1h}")


if __name__ == "__main__":
    asyncio.run(test_telemetry_flow())