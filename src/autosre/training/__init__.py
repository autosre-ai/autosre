"""
AutoSRE Training Module - Fine-tuning pipeline for enterprise customization.

This module enables enterprises to fine-tune LLMs on their own incident data,
improving model performance on organization-specific infrastructure, terminology,
and investigation patterns.

Components:
- DataCollector: Collect investigation data from incidents
- Dataset: Prepare training datasets from collected data
- FineTuner: PEFT/LoRA fine-tuning pipeline
- Evaluator: Model evaluation and benchmarking
"""

from .data_collector import (
    DataCollector,
    InvestigationRecord,
    TrainingExample,
    CollectionConfig,
)
from .dataset import (
    DatasetBuilder,
    TrainingDataset,
    DatasetConfig,
    DatasetSplit,
)
from .finetune import (
    FineTuner,
    FineTuneConfig,
    LoRAConfig,
    TrainingMetrics,
    CheckpointCallback,
)
from .evaluate import (
    ModelEvaluator,
    EvaluationResult,
    EvaluationConfig,
    BenchmarkSuite,
)

__all__ = [
    # Data Collection
    "DataCollector",
    "InvestigationRecord",
    "TrainingExample",
    "CollectionConfig",
    # Dataset Preparation
    "DatasetBuilder",
    "TrainingDataset",
    "DatasetConfig",
    "DatasetSplit",
    # Fine-tuning
    "FineTuner",
    "FineTuneConfig",
    "LoRAConfig",
    "TrainingMetrics",
    "CheckpointCallback",
    # Evaluation
    "ModelEvaluator",
    "EvaluationResult",
    "EvaluationConfig",
    "BenchmarkSuite",
]
