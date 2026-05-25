"""
Dataset - Prepare and manage training datasets for fine-tuning.

Handles dataset creation, splitting, validation, and conversion
to formats compatible with various training frameworks.
"""

import json
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Optional

from .data_collector import TrainingExample, DataCollector, CollectionConfig, DataQuality

logger = logging.getLogger(__name__)


class DatasetFormat(str, Enum):
    """Supported dataset formats."""
    
    JSONL = "jsonl"  # Standard JSONL for most frameworks
    HF_DATASET = "hf_dataset"  # Hugging Face datasets format
    OPENAI = "openai"  # OpenAI fine-tuning format
    ALPACA = "alpaca"  # Alpaca/Stanford format
    SHAREGPT = "sharegpt"  # ShareGPT conversation format


@dataclass
class DatasetSplit:
    """A split of the dataset (train, validation, test)."""
    
    name: str
    examples: list[TrainingExample]
    
    def __len__(self) -> int:
        return len(self.examples)
    
    def __iter__(self) -> Iterator[TrainingExample]:
        return iter(self.examples)
    
    def to_dict_list(self) -> list[dict[str, Any]]:
        """Convert to list of dictionaries."""
        return [ex.to_dict() for ex in self.examples]
    
    def shuffle(self, seed: Optional[int] = None) -> "DatasetSplit":
        """Return a shuffled copy of this split."""
        examples = self.examples.copy()
        if seed is not None:
            random.seed(seed)
        random.shuffle(examples)
        return DatasetSplit(name=self.name, examples=examples)
    
    def filter_by_quality(self, min_score: float) -> "DatasetSplit":
        """Filter examples by minimum quality score."""
        filtered = [ex for ex in self.examples if ex.quality_score >= min_score]
        return DatasetSplit(name=self.name, examples=filtered)
    
    def filter_by_category(self, category: str) -> "DatasetSplit":
        """Filter examples by category."""
        filtered = [ex for ex in self.examples if category in ex.categories]
        return DatasetSplit(name=self.name, examples=filtered)


@dataclass
class DatasetConfig:
    """Configuration for dataset preparation."""
    
    # Split ratios
    train_ratio: float = 0.8
    validation_ratio: float = 0.1
    test_ratio: float = 0.1
    
    # Quality filters
    min_quality_score: float = 0.5
    include_categories: Optional[list[str]] = None
    exclude_categories: Optional[list[str]] = None
    
    # Processing
    shuffle: bool = True
    random_seed: int = 42
    max_examples: Optional[int] = None
    
    # Format
    output_format: DatasetFormat = DatasetFormat.JSONL
    
    # Augmentation
    enable_augmentation: bool = False
    augmentation_factor: int = 2  # How many variants per example
    
    def __post_init__(self):
        # Validate ratios
        total = self.train_ratio + self.validation_ratio + self.test_ratio
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Split ratios must sum to 1.0, got {total}")


@dataclass
class TrainingDataset:
    """A complete training dataset with train/validation/test splits."""
    
    name: str
    train: DatasetSplit
    validation: DatasetSplit
    test: DatasetSplit
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __len__(self) -> int:
        return len(self.train) + len(self.validation) + len(self.test)
    
    def get_stats(self) -> dict[str, Any]:
        """Get dataset statistics."""
        all_examples = list(self.train) + list(self.validation) + list(self.test)
        
        # Category distribution
        category_counts: dict[str, int] = {}
        for ex in all_examples:
            for cat in ex.categories:
                category_counts[cat] = category_counts.get(cat, 0) + 1
        
        # Difficulty distribution
        difficulty_counts: dict[str, int] = {}
        for ex in all_examples:
            difficulty_counts[ex.difficulty] = difficulty_counts.get(ex.difficulty, 0) + 1
        
        # Quality score stats
        scores = [ex.quality_score for ex in all_examples]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        return {
            "total_examples": len(self),
            "train_size": len(self.train),
            "validation_size": len(self.validation),
            "test_size": len(self.test),
            "category_distribution": category_counts,
            "difficulty_distribution": difficulty_counts,
            "avg_quality_score": avg_score,
            "metadata": self.metadata,
        }
    
    def to_hf_dataset(self) -> Any:
        """Convert to Hugging Face Dataset format.
        
        Requires the 'datasets' library to be installed.
        """
        try:
            from datasets import Dataset, DatasetDict
        except ImportError:
            raise ImportError(
                "The 'datasets' library is required for HuggingFace format. "
                "Install it with: pip install datasets"
            )
        
        def examples_to_dict(examples: list[TrainingExample]) -> dict[str, list]:
            """Convert examples to columnar format."""
            return {
                "id": [ex.id for ex in examples],
                "system_prompt": [ex.system_prompt for ex in examples],
                "user_prompt": [ex.user_prompt for ex in examples],
                "assistant_response": [ex.assistant_response for ex in examples],
                "quality_score": [ex.quality_score for ex in examples],
                "difficulty": [ex.difficulty for ex in examples],
                "categories": [ex.categories for ex in examples],
            }
        
        return DatasetDict({
            "train": Dataset.from_dict(examples_to_dict(self.train.examples)),
            "validation": Dataset.from_dict(examples_to_dict(self.validation.examples)),
            "test": Dataset.from_dict(examples_to_dict(self.test.examples)),
        })


class DatasetBuilder:
    """Builds training datasets from collected investigation data.
    
    Example:
        builder = DatasetBuilder(DatasetConfig())
        
        # From collector
        collector = DataCollector(CollectionConfig(output_dir=Path("./data")))
        dataset = builder.build_from_collector(collector, name="autosre_v1")
        
        # Export
        builder.export(dataset, output_dir=Path("./datasets"))
    """
    
    def __init__(self, config: DatasetConfig):
        """Initialize the dataset builder.
        
        Args:
            config: Dataset configuration
        """
        self.config = config
    
    def build_from_collector(
        self,
        collector: DataCollector,
        name: str = "autosre_training",
    ) -> TrainingDataset:
        """Build a dataset from a data collector.
        
        Args:
            collector: DataCollector with recorded investigations
            name: Name for the dataset
            
        Returns:
            Complete TrainingDataset
        """
        # Load all records
        records = collector.load_records()
        logger.info(f"Building dataset from {len(records)} investigation records")
        
        # Generate training examples
        all_examples: list[TrainingExample] = []
        for record in records:
            examples = collector.create_training_examples(record)
            all_examples.extend(examples)
        
        logger.info(f"Generated {len(all_examples)} training examples")
        
        return self.build_from_examples(all_examples, name)
    
    def build_from_examples(
        self,
        examples: list[TrainingExample],
        name: str = "autosre_training",
    ) -> TrainingDataset:
        """Build a dataset from a list of training examples.
        
        Args:
            examples: List of training examples
            name: Name for the dataset
            
        Returns:
            Complete TrainingDataset
        """
        # Apply filters
        filtered = self._apply_filters(examples)
        logger.info(f"After filtering: {len(filtered)} examples (from {len(examples)})")
        
        # Apply augmentation if enabled
        if self.config.enable_augmentation:
            filtered = self._augment_examples(filtered)
            logger.info(f"After augmentation: {len(filtered)} examples")
        
        # Shuffle if configured
        if self.config.shuffle:
            random.seed(self.config.random_seed)
            random.shuffle(filtered)
        
        # Limit total examples if configured
        if self.config.max_examples and len(filtered) > self.config.max_examples:
            filtered = filtered[:self.config.max_examples]
            logger.info(f"Limited to {len(filtered)} examples")
        
        # Split into train/validation/test
        train_split, val_split, test_split = self._create_splits(filtered)
        
        # Create dataset
        dataset = TrainingDataset(
            name=name,
            train=DatasetSplit(name="train", examples=train_split),
            validation=DatasetSplit(name="validation", examples=val_split),
            test=DatasetSplit(name="test", examples=test_split),
            metadata={
                "config": {
                    "train_ratio": self.config.train_ratio,
                    "validation_ratio": self.config.validation_ratio,
                    "test_ratio": self.config.test_ratio,
                    "min_quality_score": self.config.min_quality_score,
                    "shuffle": self.config.shuffle,
                    "random_seed": self.config.random_seed,
                },
                "original_count": len(examples),
                "filtered_count": len(filtered),
            },
        )
        
        logger.info(f"Created dataset '{name}': {dataset.get_stats()}")
        return dataset
    
    def build_from_jsonl(
        self,
        filepath: Path,
        name: str = "autosre_training",
    ) -> TrainingDataset:
        """Build a dataset from a JSONL file.
        
        Args:
            filepath: Path to JSONL file
            name: Name for the dataset
            
        Returns:
            Complete TrainingDataset
        """
        examples = []
        
        with open(filepath) as f:
            for line in f:
                data = json.loads(line.strip())
                
                # Handle different input formats
                if "messages" in data:
                    # Chat format
                    messages = data["messages"]
                    system = next((m["content"] for m in messages if m["role"] == "system"), "")
                    user = next((m["content"] for m in messages if m["role"] == "user"), "")
                    assistant = next((m["content"] for m in messages if m["role"] == "assistant"), "")
                    
                    examples.append(TrainingExample(
                        id=data.get("id", str(len(examples))),
                        source_investigation_id=data.get("source_investigation_id", ""),
                        system_prompt=system,
                        user_prompt=user,
                        assistant_response=assistant,
                        quality_score=data.get("quality_score", 0.7),
                        difficulty=data.get("difficulty", "intermediate"),
                        categories=data.get("categories", []),
                    ))
                elif "instruction" in data and "output" in data:
                    # Instruction format
                    examples.append(TrainingExample(
                        id=data.get("id", str(len(examples))),
                        source_investigation_id="",
                        system_prompt="",
                        user_prompt=data["instruction"],
                        assistant_response=data["output"],
                        quality_score=data.get("quality_score", 0.7),
                        difficulty=data.get("difficulty", "intermediate"),
                        categories=data.get("categories", []),
                    ))
                else:
                    # Direct format
                    examples.append(TrainingExample(
                        id=data.get("id", str(len(examples))),
                        source_investigation_id=data.get("source_investigation_id", ""),
                        system_prompt=data.get("system_prompt", ""),
                        user_prompt=data.get("user_prompt", ""),
                        assistant_response=data.get("assistant_response", ""),
                        quality_score=data.get("quality_score", 0.7),
                        difficulty=data.get("difficulty", "intermediate"),
                        categories=data.get("categories", []),
                    ))
        
        logger.info(f"Loaded {len(examples)} examples from {filepath}")
        return self.build_from_examples(examples, name)
    
    def _apply_filters(
        self,
        examples: list[TrainingExample],
    ) -> list[TrainingExample]:
        """Apply configured filters to examples."""
        filtered = examples
        
        # Filter by quality score
        filtered = [
            ex for ex in filtered
            if ex.quality_score >= self.config.min_quality_score
        ]
        
        # Filter by included categories
        if self.config.include_categories:
            filtered = [
                ex for ex in filtered
                if any(cat in ex.categories for cat in self.config.include_categories)
            ]
        
        # Filter by excluded categories
        if self.config.exclude_categories:
            filtered = [
                ex for ex in filtered
                if not any(cat in ex.categories for cat in self.config.exclude_categories)
            ]
        
        return filtered
    
    def _augment_examples(
        self,
        examples: list[TrainingExample],
    ) -> list[TrainingExample]:
        """Augment examples with variations.
        
        Creates variations of high-quality examples to increase dataset size.
        """
        augmented = examples.copy()
        
        # Only augment high-quality examples
        high_quality = [ex for ex in examples if ex.quality_score >= 0.8]
        
        for ex in high_quality:
            for i in range(self.config.augmentation_factor - 1):
                # Create variation (simple paraphrase-style augmentation)
                variant = TrainingExample(
                    id=f"{ex.id}_aug{i+1}",
                    source_investigation_id=ex.source_investigation_id,
                    system_prompt=ex.system_prompt,
                    user_prompt=self._paraphrase_prompt(ex.user_prompt),
                    assistant_response=ex.assistant_response,
                    quality_score=ex.quality_score * 0.9,  # Slightly lower quality
                    difficulty=ex.difficulty,
                    categories=ex.categories + ["augmented"],
                )
                augmented.append(variant)
        
        return augmented
    
    def _paraphrase_prompt(self, prompt: str) -> str:
        """Simple paraphrase by reordering and synonym substitution."""
        # Simple transformations
        replacements = [
            ("Please investigate", "Investigate"),
            ("What is the root cause", "Identify the root cause"),
            ("Can you analyze", "Analyze"),
            ("I need help with", "Help me understand"),
            ("Alert:", "ALERT:"),
            ("Service:", "SERVICE:"),
        ]
        
        result = prompt
        # Apply one random replacement
        if replacements:
            old, new = random.choice(replacements)
            result = result.replace(old, new, 1)
        
        return result
    
    def _create_splits(
        self,
        examples: list[TrainingExample],
    ) -> tuple[list[TrainingExample], list[TrainingExample], list[TrainingExample]]:
        """Split examples into train/validation/test sets."""
        n = len(examples)
        
        train_end = int(n * self.config.train_ratio)
        val_end = train_end + int(n * self.config.validation_ratio)
        
        train = examples[:train_end]
        validation = examples[train_end:val_end]
        test = examples[val_end:]
        
        return train, validation, test
    
    def export(
        self,
        dataset: TrainingDataset,
        output_dir: Path,
        format: Optional[DatasetFormat] = None,
    ) -> dict[str, Path]:
        """Export dataset to files.
        
        Args:
            dataset: Dataset to export
            output_dir: Output directory
            format: Output format (uses config default if not specified)
            
        Returns:
            Dictionary mapping split names to file paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        format = format or self.config.output_format
        
        paths: dict[str, Path] = {}
        
        if format == DatasetFormat.JSONL:
            paths = self._export_jsonl(dataset, output_dir)
        elif format == DatasetFormat.OPENAI:
            paths = self._export_openai(dataset, output_dir)
        elif format == DatasetFormat.ALPACA:
            paths = self._export_alpaca(dataset, output_dir)
        elif format == DatasetFormat.SHAREGPT:
            paths = self._export_sharegpt(dataset, output_dir)
        elif format == DatasetFormat.HF_DATASET:
            paths = self._export_hf_dataset(dataset, output_dir)
        
        # Save metadata
        meta_path = output_dir / "metadata.json"
        with open(meta_path, "w") as f:
            json.dump(dataset.get_stats(), f, indent=2)
        paths["metadata"] = meta_path
        
        logger.info(f"Exported dataset to {output_dir}")
        return paths
    
    def _export_jsonl(
        self,
        dataset: TrainingDataset,
        output_dir: Path,
    ) -> dict[str, Path]:
        """Export in JSONL format."""
        paths = {}
        
        for split_name, split in [
            ("train", dataset.train),
            ("validation", dataset.validation),
            ("test", dataset.test),
        ]:
            filepath = output_dir / f"{split_name}.jsonl"
            with open(filepath, "w") as f:
                for ex in split:
                    f.write(json.dumps(ex.to_dict()) + "\n")
            paths[split_name] = filepath
        
        return paths
    
    def _export_openai(
        self,
        dataset: TrainingDataset,
        output_dir: Path,
    ) -> dict[str, Path]:
        """Export in OpenAI fine-tuning format."""
        paths = {}
        
        for split_name, split in [
            ("train", dataset.train),
            ("validation", dataset.validation),
        ]:
            filepath = output_dir / f"{split_name}_openai.jsonl"
            with open(filepath, "w") as f:
                for ex in split:
                    data = {"messages": ex.to_chat_format()}
                    f.write(json.dumps(data) + "\n")
            paths[split_name] = filepath
        
        return paths
    
    def _export_alpaca(
        self,
        dataset: TrainingDataset,
        output_dir: Path,
    ) -> dict[str, Path]:
        """Export in Alpaca format."""
        paths = {}
        
        for split_name, split in [
            ("train", dataset.train),
            ("validation", dataset.validation),
            ("test", dataset.test),
        ]:
            filepath = output_dir / f"{split_name}_alpaca.json"
            examples = []
            for ex in split:
                examples.append({
                    "instruction": ex.user_prompt,
                    "input": "",
                    "output": ex.assistant_response,
                })
            
            with open(filepath, "w") as f:
                json.dump(examples, f, indent=2)
            paths[split_name] = filepath
        
        return paths
    
    def _export_sharegpt(
        self,
        dataset: TrainingDataset,
        output_dir: Path,
    ) -> dict[str, Path]:
        """Export in ShareGPT format."""
        paths = {}
        
        for split_name, split in [
            ("train", dataset.train),
            ("validation", dataset.validation),
            ("test", dataset.test),
        ]:
            filepath = output_dir / f"{split_name}_sharegpt.json"
            conversations = []
            for ex in split:
                conversations.append({
                    "id": ex.id,
                    "conversations": [
                        {"from": "system", "value": ex.system_prompt},
                        {"from": "human", "value": ex.user_prompt},
                        {"from": "gpt", "value": ex.assistant_response},
                    ],
                })
            
            with open(filepath, "w") as f:
                json.dump(conversations, f, indent=2)
            paths[split_name] = filepath
        
        return paths
    
    def _export_hf_dataset(
        self,
        dataset: TrainingDataset,
        output_dir: Path,
    ) -> dict[str, Path]:
        """Export as Hugging Face dataset."""
        try:
            hf_dataset = dataset.to_hf_dataset()
            hf_dataset.save_to_disk(str(output_dir / "hf_dataset"))
            return {"hf_dataset": output_dir / "hf_dataset"}
        except ImportError:
            logger.warning("HuggingFace datasets not available, falling back to JSONL")
            return self._export_jsonl(dataset, output_dir)


def validate_dataset(dataset: TrainingDataset) -> dict[str, Any]:
    """Validate a training dataset.
    
    Checks for:
    - Minimum dataset size
    - Data quality issues
    - Format consistency
    - Potential data leakage
    
    Returns:
        Validation results with issues and warnings
    """
    issues = []
    warnings = []
    
    # Check minimum sizes
    if len(dataset.train) < 100:
        warnings.append(f"Training set is small ({len(dataset.train)} examples). Consider adding more data.")
    
    if len(dataset.validation) < 10:
        warnings.append(f"Validation set is small ({len(dataset.validation)} examples).")
    
    # Check for empty examples
    all_examples = list(dataset.train) + list(dataset.validation) + list(dataset.test)
    empty_count = sum(
        1 for ex in all_examples
        if not ex.user_prompt.strip() or not ex.assistant_response.strip()
    )
    if empty_count > 0:
        issues.append(f"Found {empty_count} examples with empty prompts or responses")
    
    # Check for duplicates
    seen_prompts = set()
    duplicate_count = 0
    for ex in all_examples:
        prompt_hash = hash(ex.user_prompt[:100])
        if prompt_hash in seen_prompts:
            duplicate_count += 1
        seen_prompts.add(prompt_hash)
    
    if duplicate_count > 0:
        warnings.append(f"Found {duplicate_count} potential duplicate examples")
    
    # Check for data leakage (same examples in train and test)
    train_ids = {ex.source_investigation_id for ex in dataset.train}
    test_ids = {ex.source_investigation_id for ex in dataset.test}
    overlap = train_ids & test_ids
    if overlap:
        issues.append(
            f"Data leakage detected: {len(overlap)} investigation IDs appear in both train and test"
        )
    
    # Check quality distribution
    low_quality = sum(1 for ex in dataset.train if ex.quality_score < 0.5)
    if low_quality > len(dataset.train) * 0.3:
        warnings.append(f"High proportion of low-quality examples in training set: {low_quality}/{len(dataset.train)}")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "stats": dataset.get_stats(),
    }
