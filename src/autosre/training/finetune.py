"""
Fine-Tuning Pipeline - PEFT/LoRA fine-tuning for AutoSRE models.

Provides a complete fine-tuning pipeline using parameter-efficient
fine-tuning (PEFT) with LoRA adapters, enabling enterprises to
customize models on their incident data without full model training.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ModelBackend(str, Enum):
    """Supported model backends for fine-tuning."""
    
    HUGGINGFACE = "huggingface"  # Local HuggingFace transformers
    OPENAI = "openai"  # OpenAI fine-tuning API
    ANTHROPIC = "anthropic"  # Anthropic fine-tuning (when available)
    TOGETHER = "together"  # Together.ai
    ANYSCALE = "anyscale"  # Anyscale


class QuantizationMode(str, Enum):
    """Quantization modes for memory-efficient training."""
    
    NONE = "none"
    INT8 = "int8"
    INT4 = "int4"
    NF4 = "nf4"  # QLoRA


@dataclass
class LoRAConfig:
    """Configuration for LoRA adapters.
    
    LoRA (Low-Rank Adaptation) enables efficient fine-tuning by
    only training small adapter layers instead of the full model.
    """
    
    # LoRA hyperparameters
    r: int = 16  # Rank of the update matrices
    lora_alpha: int = 32  # Alpha parameter for scaling
    lora_dropout: float = 0.05  # Dropout probability
    
    # Target modules (model-specific)
    target_modules: list[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ])
    
    # Additional settings
    bias: str = "none"  # "none", "all", or "lora_only"
    task_type: str = "CAUSAL_LM"
    modules_to_save: Optional[list[str]] = None  # Full modules to also train
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "r": self.r,
            "lora_alpha": self.lora_alpha,
            "lora_dropout": self.lora_dropout,
            "target_modules": self.target_modules,
            "bias": self.bias,
            "task_type": self.task_type,
            "modules_to_save": self.modules_to_save,
        }


@dataclass
class FineTuneConfig:
    """Complete fine-tuning configuration."""
    
    # Model settings
    base_model: str = "mistralai/Mistral-7B-Instruct-v0.2"
    backend: ModelBackend = ModelBackend.HUGGINGFACE
    
    # LoRA settings
    lora_config: LoRAConfig = field(default_factory=LoRAConfig)
    use_lora: bool = True
    
    # Training hyperparameters
    learning_rate: float = 2e-4
    num_epochs: int = 3
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    warmup_ratio: float = 0.03
    weight_decay: float = 0.001
    max_grad_norm: float = 0.3
    
    # Sequence settings
    max_seq_length: int = 2048
    packing: bool = False  # Pack multiple short examples
    
    # Memory optimization
    quantization: QuantizationMode = QuantizationMode.NF4
    gradient_checkpointing: bool = True
    
    # Output settings
    output_dir: Path = Path("./fine_tuned_model")
    save_steps: int = 100
    eval_steps: int = 100
    logging_steps: int = 10
    
    # Evaluation
    do_eval: bool = True
    eval_dataset_path: Optional[Path] = None
    
    # Callbacks
    early_stopping_patience: int = 3
    early_stopping_threshold: float = 0.01
    
    # Distributed training
    local_rank: int = -1
    deepspeed_config: Optional[Path] = None
    
    # W&B logging
    use_wandb: bool = False
    wandb_project: str = "autosre-finetune"
    wandb_run_name: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "base_model": self.base_model,
            "backend": self.backend.value,
            "lora_config": self.lora_config.to_dict(),
            "use_lora": self.use_lora,
            "learning_rate": self.learning_rate,
            "num_epochs": self.num_epochs,
            "batch_size": self.batch_size,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "warmup_ratio": self.warmup_ratio,
            "weight_decay": self.weight_decay,
            "max_grad_norm": self.max_grad_norm,
            "max_seq_length": self.max_seq_length,
            "packing": self.packing,
            "quantization": self.quantization.value,
            "gradient_checkpointing": self.gradient_checkpointing,
            "output_dir": str(self.output_dir),
            "save_steps": self.save_steps,
            "eval_steps": self.eval_steps,
            "logging_steps": self.logging_steps,
            "do_eval": self.do_eval,
        }


@dataclass
class TrainingMetrics:
    """Metrics collected during training."""
    
    step: int
    epoch: float
    loss: float
    learning_rate: float
    
    # Optional metrics
    eval_loss: Optional[float] = None
    eval_perplexity: Optional[float] = None
    grad_norm: Optional[float] = None
    tokens_per_second: Optional[float] = None
    gpu_memory_mb: Optional[float] = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "epoch": self.epoch,
            "loss": self.loss,
            "learning_rate": self.learning_rate,
            "eval_loss": self.eval_loss,
            "eval_perplexity": self.eval_perplexity,
            "grad_norm": self.grad_norm,
            "tokens_per_second": self.tokens_per_second,
            "gpu_memory_mb": self.gpu_memory_mb,
        }


class CheckpointCallback:
    """Callback for saving checkpoints and tracking progress."""
    
    def __init__(
        self,
        output_dir: Path,
        save_best_only: bool = True,
        metric_for_best: str = "eval_loss",
        greater_is_better: bool = False,
    ):
        self.output_dir = output_dir
        self.save_best_only = save_best_only
        self.metric_for_best = metric_for_best
        self.greater_is_better = greater_is_better
        
        self.best_metric: Optional[float] = None
        self.metrics_history: list[TrainingMetrics] = []
        
    def on_step_end(self, metrics: TrainingMetrics) -> bool:
        """Called at the end of each step.
        
        Returns:
            True if training should continue, False to stop early
        """
        self.metrics_history.append(metrics)
        
        # Log progress
        logger.info(
            f"Step {metrics.step} | Epoch {metrics.epoch:.2f} | "
            f"Loss: {metrics.loss:.4f} | LR: {metrics.learning_rate:.2e}"
        )
        
        return True
    
    def on_eval_end(self, metrics: TrainingMetrics) -> bool:
        """Called after evaluation.
        
        Returns:
            True if this is the best model so far
        """
        current = getattr(metrics, self.metric_for_best)
        if current is None:
            return False
        
        is_best = False
        if self.best_metric is None:
            is_best = True
        elif self.greater_is_better:
            is_best = current > self.best_metric
        else:
            is_best = current < self.best_metric
        
        if is_best:
            self.best_metric = current
            logger.info(f"New best {self.metric_for_best}: {current:.4f}")
        
        return is_best
    
    def save_metrics(self) -> None:
        """Save all collected metrics to disk."""
        metrics_path = self.output_dir / "training_metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(
                [m.to_dict() for m in self.metrics_history],
                f,
                indent=2,
            )


class FineTuner:
    """Fine-tuning pipeline for AutoSRE models.
    
    Supports multiple backends (HuggingFace, OpenAI, etc.) and
    provides a unified interface for fine-tuning on investigation data.
    
    Example:
        config = FineTuneConfig(
            base_model="mistralai/Mistral-7B-Instruct-v0.2",
            output_dir=Path("./my_model"),
            num_epochs=3,
        )
        
        finetuner = FineTuner(config)
        
        # Fine-tune on dataset
        result = finetuner.train(
            train_path=Path("./data/train.jsonl"),
            eval_path=Path("./data/validation.jsonl"),
        )
        
        # Export for inference
        finetuner.export_for_inference(Path("./deployed_model"))
    """
    
    def __init__(self, config: FineTuneConfig):
        """Initialize the fine-tuner.
        
        Args:
            config: Fine-tuning configuration
        """
        self.config = config
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.model = None
        self.tokenizer = None
        self.trainer = None
        self._training_start_time: Optional[datetime] = None
        
    def train(
        self,
        train_path: Path,
        eval_path: Optional[Path] = None,
        callback: Optional[CheckpointCallback] = None,
    ) -> dict[str, Any]:
        """Run fine-tuning.
        
        Args:
            train_path: Path to training data (JSONL)
            eval_path: Path to evaluation data (optional)
            callback: Checkpoint callback
            
        Returns:
            Training results with metrics
        """
        self._training_start_time = datetime.now(timezone.utc)
        
        # Route to appropriate backend
        if self.config.backend == ModelBackend.HUGGINGFACE:
            return self._train_huggingface(train_path, eval_path, callback)
        elif self.config.backend == ModelBackend.OPENAI:
            return self._train_openai(train_path, eval_path)
        elif self.config.backend == ModelBackend.TOGETHER:
            return self._train_together(train_path, eval_path)
        else:
            raise ValueError(f"Unsupported backend: {self.config.backend}")
    
    def _train_huggingface(
        self,
        train_path: Path,
        eval_path: Optional[Path],
        callback: Optional[CheckpointCallback],
    ) -> dict[str, Any]:
        """Fine-tune using HuggingFace transformers + PEFT."""
        try:
            import torch
            from transformers import (
                AutoModelForCausalLM,
                AutoTokenizer,
                TrainingArguments,
                Trainer,
                DataCollatorForLanguageModeling,
                BitsAndBytesConfig,
            )
            from peft import (
                LoraConfig,
                get_peft_model,
                prepare_model_for_kbit_training,
                TaskType,
            )
            from datasets import load_dataset
        except ImportError as e:
            raise ImportError(
                f"HuggingFace training requires additional packages: {e}\n"
                "Install with: pip install transformers peft datasets bitsandbytes"
            )
        
        logger.info(f"Starting HuggingFace fine-tuning with {self.config.base_model}")
        
        # Set up quantization config
        bnb_config = None
        if self.config.quantization == QuantizationMode.INT4:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="fp4",
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
        elif self.config.quantization == QuantizationMode.NF4:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
        elif self.config.quantization == QuantizationMode.INT8:
            bnb_config = BitsAndBytesConfig(load_in_8bit=True)
        
        # Load model
        logger.info("Loading base model...")
        model = AutoModelForCausalLM.from_pretrained(
            self.config.base_model,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
        )
        
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            self.config.base_model,
            trust_remote_code=True,
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        self.tokenizer = tokenizer
        
        # Prepare for k-bit training if quantized
        if bnb_config:
            model = prepare_model_for_kbit_training(
                model,
                use_gradient_checkpointing=self.config.gradient_checkpointing,
            )
        
        # Apply LoRA
        if self.config.use_lora:
            logger.info("Applying LoRA configuration...")
            lora_config = LoraConfig(
                r=self.config.lora_config.r,
                lora_alpha=self.config.lora_config.lora_alpha,
                lora_dropout=self.config.lora_config.lora_dropout,
                target_modules=self.config.lora_config.target_modules,
                bias=self.config.lora_config.bias,
                task_type=TaskType.CAUSAL_LM,
            )
            model = get_peft_model(model, lora_config)
            model.print_trainable_parameters()
        
        self.model = model
        
        # Load datasets
        logger.info("Loading training data...")
        train_dataset = self._load_and_tokenize_dataset(train_path, tokenizer)
        eval_dataset = None
        if eval_path:
            eval_dataset = self._load_and_tokenize_dataset(eval_path, tokenizer)
        
        # Training arguments
        training_args = TrainingArguments(
            output_dir=str(self.config.output_dir),
            num_train_epochs=self.config.num_epochs,
            per_device_train_batch_size=self.config.batch_size,
            per_device_eval_batch_size=self.config.batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            learning_rate=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
            warmup_ratio=self.config.warmup_ratio,
            max_grad_norm=self.config.max_grad_norm,
            logging_steps=self.config.logging_steps,
            save_steps=self.config.save_steps,
            eval_steps=self.config.eval_steps if eval_dataset else None,
            evaluation_strategy="steps" if eval_dataset else "no",
            save_total_limit=3,
            load_best_model_at_end=True if eval_dataset else False,
            fp16=False,
            bf16=True,
            gradient_checkpointing=self.config.gradient_checkpointing,
            report_to="wandb" if self.config.use_wandb else "none",
            run_name=self.config.wandb_run_name,
        )
        
        # Data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=tokenizer,
            mlm=False,
        )
        
        # Create trainer
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            data_collator=data_collator,
        )
        
        self.trainer = trainer
        
        # Train
        logger.info("Starting training...")
        train_result = trainer.train()
        
        # Save final model
        logger.info("Saving final model...")
        trainer.save_model()
        tokenizer.save_pretrained(self.config.output_dir)
        
        # Save training config
        config_path = self.config.output_dir / "training_config.json"
        with open(config_path, "w") as f:
            json.dump(self.config.to_dict(), f, indent=2)
        
        # Compute final metrics
        training_time = (datetime.now(timezone.utc) - self._training_start_time).total_seconds()
        
        result = {
            "status": "success",
            "training_time_seconds": training_time,
            "final_loss": train_result.training_loss,
            "total_steps": train_result.global_step,
            "model_path": str(self.config.output_dir),
            "config": self.config.to_dict(),
        }
        
        # Save results
        results_path = self.config.output_dir / "training_results.json"
        with open(results_path, "w") as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"Training complete! Model saved to {self.config.output_dir}")
        return result
    
    def _load_and_tokenize_dataset(
        self,
        path: Path,
        tokenizer: Any,
    ) -> Any:
        """Load and tokenize a JSONL dataset."""
        from datasets import load_dataset
        
        dataset = load_dataset("json", data_files=str(path), split="train")
        
        def tokenize_function(examples):
            # Format as chat
            texts = []
            for i in range(len(examples["user_prompt"])):
                system = examples.get("system_prompt", [""])[i] or ""
                user = examples["user_prompt"][i]
                assistant = examples["assistant_response"][i]
                
                # Format as instruction
                if system:
                    text = f"{system}\n\n### User:\n{user}\n\n### Assistant:\n{assistant}"
                else:
                    text = f"### User:\n{user}\n\n### Assistant:\n{assistant}"
                texts.append(text)
            
            return tokenizer(
                texts,
                truncation=True,
                max_length=self.config.max_seq_length,
                padding="max_length",
            )
        
        return dataset.map(
            tokenize_function,
            batched=True,
            remove_columns=dataset.column_names,
        )
    
    def _train_openai(
        self,
        train_path: Path,
        eval_path: Optional[Path],
    ) -> dict[str, Any]:
        """Fine-tune using OpenAI API."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("OpenAI training requires: pip install openai")
        
        client = OpenAI()
        
        logger.info("Uploading training file to OpenAI...")
        
        # Upload training file
        with open(train_path, "rb") as f:
            train_file = client.files.create(file=f, purpose="fine-tune")
        
        # Upload validation file if provided
        val_file_id = None
        if eval_path:
            with open(eval_path, "rb") as f:
                val_file = client.files.create(file=f, purpose="fine-tune")
                val_file_id = val_file.id
        
        # Create fine-tuning job
        logger.info("Creating fine-tuning job...")
        job = client.fine_tuning.jobs.create(
            training_file=train_file.id,
            validation_file=val_file_id,
            model=self.config.base_model,
            hyperparameters={
                "n_epochs": self.config.num_epochs,
            },
        )
        
        logger.info(f"Fine-tuning job created: {job.id}")
        logger.info("Monitor progress at: https://platform.openai.com/finetune")
        
        # Poll for completion
        import time
        while True:
            job = client.fine_tuning.jobs.retrieve(job.id)
            logger.info(f"Status: {job.status}")
            
            if job.status == "succeeded":
                break
            elif job.status in ("failed", "cancelled"):
                raise RuntimeError(f"Fine-tuning failed: {job.error}")
            
            time.sleep(60)
        
        training_time = (datetime.now(timezone.utc) - self._training_start_time).total_seconds()
        
        return {
            "status": "success",
            "training_time_seconds": training_time,
            "job_id": job.id,
            "model_id": job.fine_tuned_model,
            "config": self.config.to_dict(),
        }
    
    def _train_together(
        self,
        train_path: Path,
        eval_path: Optional[Path],
    ) -> dict[str, Any]:
        """Fine-tune using Together.ai API."""
        try:
            import together
        except ImportError:
            raise ImportError("Together.ai training requires: pip install together")
        
        logger.info("Starting Together.ai fine-tuning...")
        
        # Upload training file
        file_resp = together.Files.upload(file=str(train_path))
        
        # Create fine-tuning job
        job_resp = together.FineTuning.create(
            training_file=file_resp["id"],
            model=self.config.base_model,
            n_epochs=self.config.num_epochs,
            learning_rate=self.config.learning_rate,
            batch_size=self.config.batch_size,
        )
        
        job_id = job_resp["id"]
        logger.info(f"Fine-tuning job created: {job_id}")
        
        # Poll for completion
        import time
        while True:
            status = together.FineTuning.retrieve(job_id)
            logger.info(f"Status: {status['status']}")
            
            if status["status"] == "completed":
                break
            elif status["status"] in ("failed", "cancelled"):
                raise RuntimeError(f"Fine-tuning failed: {status}")
            
            time.sleep(60)
        
        training_time = (datetime.now(timezone.utc) - self._training_start_time).total_seconds()
        
        return {
            "status": "success",
            "training_time_seconds": training_time,
            "job_id": job_id,
            "model_id": status["output_model"],
            "config": self.config.to_dict(),
        }
    
    def export_for_inference(
        self,
        output_path: Path,
        merge_lora: bool = True,
    ) -> Path:
        """Export the fine-tuned model for inference.
        
        Args:
            output_path: Where to save the exported model
            merge_lora: Whether to merge LoRA weights into base model
            
        Returns:
            Path to the exported model
        """
        if self.config.backend != ModelBackend.HUGGINGFACE:
            logger.warning("Export only supported for HuggingFace backend")
            return self.config.output_dir
        
        output_path.mkdir(parents=True, exist_ok=True)
        
        if merge_lora and self.config.use_lora:
            logger.info("Merging LoRA weights into base model...")
            
            try:
                from peft import PeftModel
                from transformers import AutoModelForCausalLM, AutoTokenizer
                import torch
                
                # Load base model
                base_model = AutoModelForCausalLM.from_pretrained(
                    self.config.base_model,
                    torch_dtype=torch.bfloat16,
                    device_map="auto",
                )
                
                # Load LoRA adapter
                model = PeftModel.from_pretrained(base_model, self.config.output_dir)
                
                # Merge and unload
                model = model.merge_and_unload()
                
                # Save merged model
                model.save_pretrained(output_path)
                
                # Copy tokenizer
                tokenizer = AutoTokenizer.from_pretrained(self.config.output_dir)
                tokenizer.save_pretrained(output_path)
                
                logger.info(f"Merged model saved to {output_path}")
                
            except Exception as e:
                logger.error(f"Failed to merge LoRA: {e}")
                logger.info("Copying adapter model instead...")
                import shutil
                shutil.copytree(self.config.output_dir, output_path, dirs_exist_ok=True)
        else:
            # Just copy the model
            import shutil
            shutil.copytree(self.config.output_dir, output_path, dirs_exist_ok=True)
        
        return output_path
    
    def push_to_hub(
        self,
        repo_id: str,
        private: bool = True,
        commit_message: str = "Upload fine-tuned AutoSRE model",
    ) -> str:
        """Push the fine-tuned model to Hugging Face Hub.
        
        Args:
            repo_id: Repository ID (e.g., "my-org/autosre-finetuned")
            private: Whether to make the repo private
            commit_message: Commit message
            
        Returns:
            URL to the uploaded model
        """
        if self.config.backend != ModelBackend.HUGGINGFACE:
            raise ValueError("Push to Hub only supported for HuggingFace backend")
        
        try:
            from huggingface_hub import HfApi
        except ImportError:
            raise ImportError("Pushing requires: pip install huggingface_hub")
        
        api = HfApi()
        
        logger.info(f"Pushing model to {repo_id}...")
        
        url = api.upload_folder(
            folder_path=str(self.config.output_dir),
            repo_id=repo_id,
            repo_type="model",
            commit_message=commit_message,
            private=private,
        )
        
        logger.info(f"Model uploaded: {url}")
        return url


def estimate_training_resources(
    config: FineTuneConfig,
    dataset_size: int,
) -> dict[str, Any]:
    """Estimate training resources required.
    
    Args:
        config: Fine-tuning configuration
        dataset_size: Number of training examples
        
    Returns:
        Resource estimates
    """
    # Rough estimates based on model size
    model_size_map = {
        "7B": {"base_vram_gb": 14, "train_vram_gb": 24, "params_b": 7},
        "13B": {"base_vram_gb": 26, "train_vram_gb": 48, "params_b": 13},
        "70B": {"base_vram_gb": 140, "train_vram_gb": 320, "params_b": 70},
    }
    
    # Detect model size from name
    size_key = "7B"
    for key in model_size_map:
        if key.lower() in config.base_model.lower():
            size_key = key
            break
    
    base_info = model_size_map[size_key]
    
    # Adjust for quantization
    vram_factor = 1.0
    if config.quantization == QuantizationMode.INT8:
        vram_factor = 0.5
    elif config.quantization in (QuantizationMode.INT4, QuantizationMode.NF4):
        vram_factor = 0.25
    
    # Adjust for LoRA
    if config.use_lora:
        vram_factor *= 0.6  # LoRA significantly reduces memory
    
    estimated_vram = base_info["train_vram_gb"] * vram_factor
    
    # Estimate training time (very rough)
    # Assume ~1000 tokens/second on a single A100
    avg_tokens_per_example = 500
    total_tokens = dataset_size * avg_tokens_per_example * config.num_epochs
    estimated_hours = total_tokens / (1000 * 3600)
    
    # Adjust for batch size and accumulation
    effective_batch = config.batch_size * config.gradient_accumulation_steps
    estimated_hours *= (4 / effective_batch)  # Normalized to batch size 4
    
    return {
        "model_size": size_key,
        "estimated_vram_gb": round(estimated_vram, 1),
        "estimated_training_hours": round(estimated_hours, 1),
        "total_training_tokens": total_tokens,
        "recommended_gpu": "A100-40GB" if estimated_vram < 40 else "A100-80GB",
        "trainable_params_estimate": f"{base_info['params_b'] * 0.01:.2f}B" if config.use_lora else f"{base_info['params_b']}B",
        "quantization": config.quantization.value,
        "lora_enabled": config.use_lora,
    }
