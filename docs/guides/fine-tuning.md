# Fine-tuning AutoSRE Models

This guide explains how to fine-tune language models on your organization's incident data to improve AutoSRE's performance on your specific infrastructure, terminology, and investigation patterns.

## Overview

Fine-tuning enables you to:

- **Customize for your infrastructure**: Train on your specific services, tools, and configurations
- **Learn your playbooks**: Capture your team's investigation patterns and best practices
- **Improve accuracy**: Reduce false positives and improve root cause identification
- **Adapt terminology**: Use your organization's specific terminology and naming conventions

## Prerequisites

Before starting, ensure you have:

1. **Hardware Requirements**:
   - GPU with at least 16GB VRAM (24GB+ recommended for 7B models)
   - Or use cloud providers (AWS, GCP, Together.ai)

2. **Software Requirements**:
   ```bash
   pip install autosre[training]
   # Or install training dependencies manually:
   pip install transformers peft datasets bitsandbytes accelerate
   ```

3. **Data Requirements**:
   - Minimum 100 investigation examples (500+ recommended)
   - High-quality, verified resolutions
   - Diverse incident types

## Quick Start

### 1. Collect Training Data

```python
from autosre.training import DataCollector, CollectionConfig
from pathlib import Path

# Initialize collector
config = CollectionConfig(
    output_dir=Path("./training_data"),
    anonymize_pii=True,
    min_quality="medium",
)
collector = DataCollector(config)

# Record an investigation
from autosre.training import ReasoningStep, InvestigationOutcome

collector.record_investigation(
    alert_name="High CPU Usage",
    alert_severity="warning",
    alert_description="CPU usage on api-server exceeded 85%",
    service="api-server",
    environment="production",
    initial_context="Alert triggered at 14:30 UTC",
    reasoning_steps=[
        ReasoningStep(
            thought="First, check current pod status",
            action="kubectl get pods -l app=api-server",
            observation="3 pods running, all showing high CPU",
        ),
        ReasoningStep(
            thought="Check recent deployments",
            action="kubectl rollout history deployment/api-server",
            observation="New deployment 2 hours ago",
        ),
        ReasoningStep(
            thought="Compare metrics before and after deployment",
            observation="CPU spike correlates with deployment time",
        ),
    ],
    hypothesis="New deployment introduced CPU-intensive code",
    root_cause="Inefficient database query in new endpoint",
    resolution="Rolled back deployment, optimized query",
    outcome=InvestigationOutcome.RESOLVED,
    time_to_resolution_minutes=45,
)
```

### 2. Generate Synthetic Data (Optional)

For bootstrapping, you can generate synthetic training data:

```bash
python scripts/prepare_training_data.py \
    --source synthetic \
    --count 500 \
    --output ./training_data \
    --format jsonl
```

### 3. Prepare the Dataset

```python
from autosre.training import DatasetBuilder, DatasetConfig, DatasetFormat

config = DatasetConfig(
    train_ratio=0.8,
    validation_ratio=0.1,
    test_ratio=0.1,
    min_quality_score=0.6,
    shuffle=True,
    output_format=DatasetFormat.JSONL,
)

builder = DatasetBuilder(config)
dataset = builder.build_from_collector(collector, name="my_org_sre")

# Export for training
builder.export(dataset, Path("./datasets/my_org_sre"))
```

### 4. Fine-tune the Model

```python
from autosre.training import FineTuner, FineTuneConfig, LoRAConfig
from pathlib import Path

# Configure fine-tuning
config = FineTuneConfig(
    # Model
    base_model="mistralai/Mistral-7B-Instruct-v0.2",
    
    # LoRA settings (recommended for efficiency)
    use_lora=True,
    lora_config=LoRAConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
    ),
    
    # Training hyperparameters
    learning_rate=2e-4,
    num_epochs=3,
    batch_size=4,
    gradient_accumulation_steps=4,
    
    # Memory optimization
    quantization="nf4",  # QLoRA for memory efficiency
    gradient_checkpointing=True,
    
    # Output
    output_dir=Path("./fine_tuned_model"),
)

# Initialize and train
finetuner = FineTuner(config)
result = finetuner.train(
    train_path=Path("./datasets/my_org_sre/train.jsonl"),
    eval_path=Path("./datasets/my_org_sre/validation.jsonl"),
)

print(f"Training complete! Final loss: {result['final_loss']:.4f}")
```

### 5. Evaluate the Model

```python
from autosre.training import ModelEvaluator, EvaluationConfig, create_sre_benchmark

config = EvaluationConfig(
    model_path=Path("./fine_tuned_model"),
    base_model="mistralai/Mistral-7B-Instruct-v0.2",  # For comparison
    output_dir=Path("./eval_results"),
)

evaluator = ModelEvaluator(config)
benchmark = create_sre_benchmark()

# Run evaluation
results = evaluator.evaluate(benchmark)

# Compare with base model
comparison = evaluator.compare_with_base(benchmark)

# Generate report
report = evaluator.generate_report(results)
print(report)
```

## Data Collection Best Practices

### What to Include

1. **Diverse Incident Types**:
   - Infrastructure issues (CPU, memory, disk, network)
   - Application errors (crashes, exceptions, timeouts)
   - Dependency failures (database, cache, external APIs)
   - Configuration problems (secrets, limits, permissions)

2. **Complete Reasoning Chains**:
   - Document each investigation step
   - Include tool outputs and observations
   - Capture the logical flow of reasoning

3. **Verified Resolutions**:
   - Only include incidents with confirmed root causes
   - Document what actually fixed the issue
   - Include time to resolution

### Quality Guidelines

| Quality Level | Criteria |
|---------------|----------|
| **High** | Expert-verified, 5+ reasoning steps, clear root cause, documented resolution |
| **Medium** | Complete investigation, reasonable root cause, resolution applied |
| **Low** | Partial investigation, unclear root cause, needs review |

### Data Anonymization

The data collector automatically anonymizes:

- IP addresses → `[IP_ADDRESS]`
- Email addresses → `[EMAIL]`
- Internal hostnames → `[INTERNAL_HOST]`
- Production-specific identifiers

You can customize patterns in the collector configuration.

## Fine-tuning Options

### Model Selection

| Model | VRAM Required | Training Time | Quality |
|-------|---------------|---------------|---------|
| Mistral-7B | 16-24GB | ~2 hours | Good |
| Llama-2-13B | 24-48GB | ~4 hours | Better |
| Llama-2-70B | 80GB+ | ~12 hours | Best |

### LoRA Configuration

LoRA enables efficient fine-tuning by only training adapter layers:

```python
LoRAConfig(
    r=16,           # Rank (8-64, higher = more parameters)
    lora_alpha=32,  # Scaling factor (usually 2x r)
    lora_dropout=0.05,
    target_modules=[  # Which layers to adapt
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
)
```

### Quantization Options

| Mode | VRAM Reduction | Quality Impact |
|------|----------------|----------------|
| None | 0% | Full precision |
| int8 | 50% | Minimal |
| int4/nf4 | 75% | Small |

QLoRA (nf4) is recommended for most users:

```python
FineTuneConfig(
    quantization="nf4",
    gradient_checkpointing=True,
)
```

## Cloud Training

### OpenAI Fine-tuning

```python
config = FineTuneConfig(
    backend="openai",
    base_model="gpt-3.5-turbo",
    num_epochs=3,
)

finetuner = FineTuner(config)
result = finetuner.train(
    train_path=Path("./datasets/train_openai.jsonl"),
)

# Use the fine-tuned model
model_id = result["model_id"]
```

### Together.ai

```python
config = FineTuneConfig(
    backend="together",
    base_model="mistralai/Mistral-7B-Instruct-v0.2",
    num_epochs=3,
)
```

## Deployment

### Export for Inference

```python
# Merge LoRA weights into base model
finetuner.export_for_inference(
    output_path=Path("./deployed_model"),
    merge_lora=True,
)
```

### Push to Hugging Face Hub

```python
finetuner.push_to_hub(
    repo_id="my-org/autosre-finetuned",
    private=True,
)
```

### Use in AutoSRE

```python
from autosre import Orchestrator

# Use local model
orchestrator = Orchestrator(
    model_path="./deployed_model",
)

# Or use HuggingFace model
orchestrator = Orchestrator(
    model="my-org/autosre-finetuned",
)
```

## Evaluation Benchmarks

### Standard Benchmarks

The evaluation module includes benchmarks for:

1. **Root Cause Identification**: Accuracy of identifying root causes
2. **Reasoning Quality**: Coherence and completeness of reasoning chains
3. **Tool Usage**: Correct selection and use of investigation tools
4. **Response Quality**: Language quality metrics (BLEU, ROUGE)

### Custom Benchmarks

Create domain-specific benchmarks:

```python
from autosre.training import BenchmarkSuite, BenchmarkCase

benchmark = BenchmarkSuite(
    name="my_org_benchmark",
    description="Custom benchmark for our infrastructure",
    cases=[
        BenchmarkCase(
            id="custom_001",
            category="root_cause",
            input="Alert: Redis cache miss rate is 80%...",
            expected_output="Root cause: Cache invalidation bug...",
            difficulty="hard",
            tags=["redis", "cache"],
        ),
        # Add more cases...
    ],
)

benchmark.save(Path("./benchmarks/my_org.jsonl"))
```

## Troubleshooting

### Out of Memory

1. Reduce batch size
2. Enable gradient checkpointing
3. Use more aggressive quantization (nf4)
4. Reduce max sequence length

```python
FineTuneConfig(
    batch_size=1,  # Minimum
    gradient_accumulation_steps=16,  # Effective batch = 16
    quantization="nf4",
    gradient_checkpointing=True,
    max_seq_length=1024,  # Reduced
)
```

### Poor Quality Results

1. **Check data quality**: Use `validate_dataset()` function
2. **Increase training data**: Aim for 500+ examples
3. **Adjust learning rate**: Try 1e-4 to 3e-4 range
4. **Train longer**: Increase epochs (3-5)
5. **Review data balance**: Ensure diverse incident types

### Slow Training

1. Use larger batch sizes if VRAM allows
2. Enable mixed precision (bf16)
3. Consider distributed training with DeepSpeed
4. Use gradient accumulation instead of larger batches

## Best Practices

1. **Start Small**: Begin with 100-200 high-quality examples
2. **Iterate**: Fine-tune, evaluate, add more data, repeat
3. **Monitor Metrics**: Track eval loss and benchmark scores
4. **Compare with Base**: Always measure improvement over base model
5. **Version Control**: Tag model versions with training data hashes
6. **Regular Updates**: Re-train quarterly with new incident data

## API Reference

See the full API documentation:

- [DataCollector](../reference/api.md#datacollector)
- [DatasetBuilder](../reference/api.md#datasetbuilder)
- [FineTuner](../reference/api.md#finetuner)
- [ModelEvaluator](../reference/api.md#modelevaluator)

## Examples

Full example notebooks are available in the `examples/` directory:

- `examples/fine_tuning_quickstart.ipynb`
- `examples/custom_benchmark_evaluation.ipynb`
- `examples/cloud_training.ipynb`
