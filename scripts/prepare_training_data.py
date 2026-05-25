#!/usr/bin/env python3
"""
Prepare Training Data for AutoSRE Fine-tuning

This script collects investigation data and prepares it for fine-tuning.
It can:
- Import from existing investigation logs
- Generate synthetic examples from templates
- Export to various training formats

Usage:
    python scripts/prepare_training_data.py --source logs --output ./training_data
    python scripts/prepare_training_data.py --source synthetic --count 100
    python scripts/prepare_training_data.py --import-jsonl ./raw_data.jsonl
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import random

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from autosre.training import (
    DataCollector,
    CollectionConfig,
    DatasetBuilder,
    DatasetConfig,
    DatasetFormat,
    InvestigationOutcome,
    DataQuality,
    ReasoningStep,
    ToolCall,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Synthetic data templates for generating training examples
ALERT_TEMPLATES = [
    {
        "name": "High CPU Usage",
        "severity": "warning",
        "description": "CPU usage on {service} has exceeded {threshold}% for the last {duration} minutes.",
        "service_types": ["api-server", "worker", "backend"],
        "root_causes": [
            "Inefficient algorithm in recent deployment",
            "Increased traffic without autoscaling",
            "Memory leak causing garbage collection pressure",
            "Runaway process or infinite loop",
        ],
    },
    {
        "name": "High Memory Usage",
        "severity": "critical",
        "description": "Memory usage on {service} is at {usage}%, approaching OOM threshold.",
        "service_types": ["cache-service", "api-server", "data-processor"],
        "root_causes": [
            "Memory leak in application code",
            "Unbounded cache growth",
            "Large query result sets not being paginated",
            "Connection pool not releasing connections",
        ],
    },
    {
        "name": "Pod CrashLoopBackOff",
        "severity": "critical",
        "description": "{count} pods in {service} deployment are in CrashLoopBackOff state.",
        "service_types": ["api-gateway", "auth-service", "payment-service"],
        "root_causes": [
            "Missing configuration or secrets",
            "Database connection failure",
            "Incompatible library version",
            "Liveness probe misconfiguration",
        ],
    },
    {
        "name": "High Error Rate",
        "severity": "warning",
        "description": "Error rate for {service} has increased to {rate}% (threshold: {threshold}%).",
        "service_types": ["api-server", "checkout-service", "search-service"],
        "root_causes": [
            "Downstream service degradation",
            "Database query timeout",
            "Rate limiting by external API",
            "Invalid input data from upstream",
        ],
    },
    {
        "name": "High Latency",
        "severity": "warning",
        "description": "P99 latency for {service} is {latency}ms (SLO: {slo}ms).",
        "service_types": ["api-gateway", "search-service", "recommendation-engine"],
        "root_causes": [
            "Database slow queries",
            "Network congestion",
            "Cold cache after restart",
            "Upstream service degradation",
        ],
    },
]

INVESTIGATION_STEPS = [
    "First, I'll check the current state of the affected pods.",
    "Let me query Prometheus for the relevant metrics.",
    "I'll examine the recent deployment history.",
    "Checking the application logs for errors.",
    "Looking at the dependency health status.",
    "Analyzing the traffic patterns.",
    "Reviewing the resource utilization trends.",
    "Checking for any recent configuration changes.",
    "Examining the network connectivity.",
    "Looking at the database connection pool status.",
]

RESOLUTION_TEMPLATES = [
    "Rolled back to the previous deployment version.",
    "Increased the resource limits for the affected pods.",
    "Restarted the affected service with cleared cache.",
    "Fixed the configuration and redeployed.",
    "Scaled up the number of replicas.",
    "Applied a hotfix for the identified bug.",
    "Cleared the stuck jobs from the queue.",
    "Reset the database connection pool.",
    "Updated the timeout configuration.",
    "Enabled rate limiting on the affected endpoint.",
]


def generate_synthetic_investigation() -> dict[str, Any]:
    """Generate a synthetic investigation record."""
    template = random.choice(ALERT_TEMPLATES)
    service = random.choice(template["service_types"])
    root_cause = random.choice(template["root_causes"])
    
    # Generate alert description with filled placeholders
    description = template["description"].format(
        service=service,
        threshold=random.randint(70, 95),
        duration=random.choice([5, 10, 15, 30]),
        usage=random.randint(80, 99),
        count=random.randint(1, 5),
        rate=random.uniform(5, 30),
        latency=random.randint(500, 5000),
        slo=random.randint(100, 500),
    )
    
    # Generate reasoning steps
    num_steps = random.randint(3, 7)
    selected_steps = random.sample(INVESTIGATION_STEPS, num_steps)
    
    reasoning_steps = []
    for i, thought in enumerate(selected_steps):
        # Add some tool calls
        tool_calls = []
        if "prometheus" in thought.lower() or "metrics" in thought.lower():
            tool_calls.append(ToolCall(
                tool_name="query_prometheus",
                arguments={"query": f"rate({service}_requests_total[5m])"},
                result={"value": random.uniform(10, 1000)},
                timestamp=datetime.utcnow(),
                duration_ms=random.randint(50, 500),
            ))
        elif "logs" in thought.lower():
            tool_calls.append(ToolCall(
                tool_name="get_logs",
                arguments={"service": service, "limit": 100},
                result={"log_count": random.randint(50, 200)},
                timestamp=datetime.utcnow(),
                duration_ms=random.randint(100, 1000),
            ))
        elif "pods" in thought.lower():
            tool_calls.append(ToolCall(
                tool_name="kubectl_get_pods",
                arguments={"namespace": "production", "label": f"app={service}"},
                result={"running": random.randint(1, 5), "pending": random.randint(0, 2)},
                timestamp=datetime.utcnow(),
                duration_ms=random.randint(50, 200),
            ))
        
        observation = f"Found relevant data indicating {root_cause.lower()}" if i == num_steps - 1 else f"Step {i+1} completed, proceeding with investigation."
        
        reasoning_steps.append(ReasoningStep(
            thought=thought,
            action=f"Executing investigation step {i+1}",
            observation=observation,
            tool_calls=tool_calls,
            timestamp=datetime.utcnow() + timedelta(minutes=i),
        ))
    
    # Generate hypothesis and resolution
    hypothesis = f"Based on the investigation, the issue appears to be caused by {root_cause.lower()}."
    resolution = random.choice(RESOLUTION_TEMPLATES)
    
    return {
        "alert_name": template["name"],
        "alert_severity": template["severity"],
        "alert_description": description,
        "service": service,
        "environment": random.choice(["production", "staging"]),
        "initial_context": f"Alert triggered for {service} in the {random.choice(['us-east-1', 'us-west-2', 'eu-west-1'])} region.",
        "reasoning_steps": reasoning_steps,
        "hypothesis": hypothesis,
        "root_cause": root_cause,
        "resolution": resolution,
        "outcome": InvestigationOutcome.RESOLVED,
        "time_to_resolution_minutes": random.randint(10, 120),
        "tags": [template["name"].lower().replace(" ", "_"), service],
    }


def import_from_jsonl(filepath: Path, collector: DataCollector) -> int:
    """Import investigation data from JSONL file."""
    count = 0
    
    with open(filepath) as f:
        for line in f:
            try:
                data = json.loads(line)
                
                # Convert to reasoning steps if needed
                reasoning_steps = []
                if "reasoning_steps" in data:
                    for step in data["reasoning_steps"]:
                        reasoning_steps.append(ReasoningStep(
                            thought=step.get("thought", ""),
                            action=step.get("action"),
                            observation=step.get("observation"),
                            timestamp=datetime.fromisoformat(step["timestamp"]) if step.get("timestamp") else None,
                        ))
                elif "reasoning" in data:
                    # Simple text format
                    for i, line in enumerate(data["reasoning"].split("\n")):
                        if line.strip():
                            reasoning_steps.append(ReasoningStep(thought=line.strip()))
                
                collector.record_investigation(
                    alert_name=data.get("alert_name", "Unknown Alert"),
                    alert_severity=data.get("alert_severity", "warning"),
                    alert_description=data.get("alert_description", ""),
                    service=data.get("service", "unknown"),
                    environment=data.get("environment", "production"),
                    initial_context=data.get("initial_context", ""),
                    reasoning_steps=reasoning_steps,
                    hypothesis=data.get("hypothesis", ""),
                    root_cause=data.get("root_cause", ""),
                    resolution=data.get("resolution", ""),
                    outcome=InvestigationOutcome(data.get("outcome", "resolved")),
                    time_to_resolution_minutes=data.get("time_to_resolution_minutes", 30),
                    tags=data.get("tags", []),
                )
                count += 1
                
            except Exception as e:
                logger.warning(f"Failed to import line: {e}")
    
    return count


def main():
    parser = argparse.ArgumentParser(description="Prepare training data for AutoSRE fine-tuning")
    
    parser.add_argument(
        "--source",
        choices=["synthetic", "import"],
        default="synthetic",
        help="Data source: synthetic (generate) or import (from file)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of synthetic examples to generate",
    )
    parser.add_argument(
        "--import-jsonl",
        type=Path,
        help="Path to JSONL file to import",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./training_data"),
        help="Output directory for training data",
    )
    parser.add_argument(
        "--format",
        choices=["jsonl", "openai", "alpaca", "sharegpt"],
        default="jsonl",
        help="Output format for the dataset",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.8,
        help="Ratio of data for training set",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--min-quality",
        type=float,
        default=0.5,
        help="Minimum quality score for examples (0-1)",
    )
    
    args = parser.parse_args()
    
    # Set random seed
    random.seed(args.seed)
    
    # Initialize collector
    config = CollectionConfig(
        output_dir=args.output / "raw",
        min_quality=DataQuality.LOW,  # Collect all, filter later
        anonymize_pii=True,
    )
    collector = DataCollector(config)
    
    # Collect data based on source
    if args.source == "synthetic":
        logger.info(f"Generating {args.count} synthetic investigation records...")
        
        for i in range(args.count):
            data = generate_synthetic_investigation()
            collector.record_investigation(**data)
            
            if (i + 1) % 10 == 0:
                logger.info(f"Generated {i + 1}/{args.count} records")
        
        logger.info(f"Generated {args.count} synthetic records")
        
    elif args.source == "import":
        if not args.import_jsonl:
            parser.error("--import-jsonl is required when using --source import")
        
        logger.info(f"Importing data from {args.import_jsonl}...")
        count = import_from_jsonl(args.import_jsonl, collector)
        logger.info(f"Imported {count} records")
    
    # Show collection statistics
    stats = collector.get_statistics()
    logger.info(f"Collection statistics: {json.dumps(stats, indent=2)}")
    
    # Build dataset
    format_map = {
        "jsonl": DatasetFormat.JSONL,
        "openai": DatasetFormat.OPENAI,
        "alpaca": DatasetFormat.ALPACA,
        "sharegpt": DatasetFormat.SHAREGPT,
    }
    
    dataset_config = DatasetConfig(
        train_ratio=args.train_ratio,
        validation_ratio=(1 - args.train_ratio) / 2,
        test_ratio=(1 - args.train_ratio) / 2,
        min_quality_score=args.min_quality,
        shuffle=True,
        random_seed=args.seed,
        output_format=format_map[args.format],
    )
    
    builder = DatasetBuilder(dataset_config)
    dataset = builder.build_from_collector(collector, name="autosre_training")
    
    # Export dataset
    output_paths = builder.export(dataset, args.output / "dataset")
    
    # Print summary
    print("\n" + "=" * 60)
    print("Training Data Preparation Complete")
    print("=" * 60)
    print(f"\nDataset Statistics:")
    for key, value in dataset.get_stats().items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")
    
    print(f"\nOutput Files:")
    for name, path in output_paths.items():
        print(f"  {name}: {path}")
    
    print("\nNext Steps:")
    print("1. Review the generated data for quality")
    print("2. Run fine-tuning with:")
    print(f"   autosre train --data {args.output / 'dataset'}")
    print("3. Evaluate the fine-tuned model")


if __name__ == "__main__":
    main()
