"""
Model Evaluation - Evaluate fine-tuned models on SRE tasks.

Provides comprehensive evaluation capabilities including:
- Standard NLP metrics (perplexity, BLEU, etc.)
- SRE-specific benchmarks (root cause accuracy, tool usage)
- A/B comparison between models
- Human evaluation integration
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EvaluationType(str, Enum):
    """Types of evaluation."""
    
    PERPLEXITY = "perplexity"  # Language modeling quality
    GENERATION = "generation"  # Free-form generation quality
    CLASSIFICATION = "classification"  # Classification accuracy
    EXTRACTION = "extraction"  # Information extraction
    REASONING = "reasoning"  # Multi-step reasoning
    TOOL_USE = "tool_use"  # Tool selection and usage
    ROOT_CAUSE = "root_cause"  # Root cause identification


@dataclass
class EvaluationConfig:
    """Configuration for model evaluation."""
    
    # Model settings
    model_path: Path
    base_model: Optional[str] = None  # For comparison
    
    # Evaluation settings
    eval_types: list[EvaluationType] = field(default_factory=lambda: [
        EvaluationType.PERPLEXITY,
        EvaluationType.GENERATION,
        EvaluationType.ROOT_CAUSE,
    ])
    
    # Generation settings
    max_new_tokens: int = 512
    temperature: float = 0.1
    top_p: float = 0.95
    num_samples: int = 3  # For generation diversity
    
    # Batch settings
    batch_size: int = 4
    max_eval_samples: Optional[int] = None
    
    # Output
    output_dir: Path = Path("./eval_results")
    save_predictions: bool = True
    
    # Human evaluation
    enable_human_eval: bool = False
    human_eval_samples: int = 50


@dataclass
class EvaluationResult:
    """Results from a single evaluation."""
    
    eval_type: EvaluationType
    score: float  # Primary score (0-1 or raw value)
    metrics: dict[str, float]  # All metrics
    samples: list[dict[str, Any]]  # Sample predictions
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "eval_type": self.eval_type.value,
            "score": self.score,
            "metrics": self.metrics,
            "samples": self.samples[:10],  # Limit samples in output
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class BenchmarkCase:
    """A single benchmark test case."""
    
    id: str
    category: str
    input: str
    expected_output: str
    context: Optional[str] = None
    difficulty: str = "medium"
    tags: list[str] = field(default_factory=list)
    
    # For classification/extraction
    expected_labels: Optional[list[str]] = None
    expected_entities: Optional[list[str]] = None
    
    # For tool use
    expected_tools: Optional[list[str]] = None


@dataclass
class BenchmarkSuite:
    """A collection of benchmark cases for evaluation."""
    
    name: str
    description: str
    cases: list[BenchmarkCase]
    version: str = "1.0"
    
    def __len__(self) -> int:
        return len(self.cases)
    
    def filter_by_category(self, category: str) -> "BenchmarkSuite":
        """Filter cases by category."""
        filtered = [c for c in self.cases if c.category == category]
        return BenchmarkSuite(
            name=f"{self.name}_{category}",
            description=f"{self.description} (filtered by {category})",
            cases=filtered,
            version=self.version,
        )
    
    def filter_by_difficulty(self, difficulty: str) -> "BenchmarkSuite":
        """Filter cases by difficulty."""
        filtered = [c for c in self.cases if c.difficulty == difficulty]
        return BenchmarkSuite(
            name=f"{self.name}_{difficulty}",
            description=f"{self.description} (filtered by {difficulty})",
            cases=filtered,
            version=self.version,
        )
    
    @classmethod
    def from_jsonl(cls, path: Path, name: str = "custom") -> "BenchmarkSuite":
        """Load benchmark suite from JSONL file."""
        cases = []
        with open(path) as f:
            for line in f:
                data = json.loads(line)
                cases.append(BenchmarkCase(
                    id=data.get("id", str(len(cases))),
                    category=data.get("category", "general"),
                    input=data["input"],
                    expected_output=data["expected_output"],
                    context=data.get("context"),
                    difficulty=data.get("difficulty", "medium"),
                    tags=data.get("tags", []),
                    expected_labels=data.get("expected_labels"),
                    expected_entities=data.get("expected_entities"),
                    expected_tools=data.get("expected_tools"),
                ))
        
        return cls(
            name=name,
            description=f"Custom benchmark from {path}",
            cases=cases,
        )
    
    def save(self, path: Path) -> None:
        """Save benchmark suite to JSONL file."""
        with open(path, "w") as f:
            for case in self.cases:
                data = {
                    "id": case.id,
                    "category": case.category,
                    "input": case.input,
                    "expected_output": case.expected_output,
                    "context": case.context,
                    "difficulty": case.difficulty,
                    "tags": case.tags,
                }
                if case.expected_labels:
                    data["expected_labels"] = case.expected_labels
                if case.expected_entities:
                    data["expected_entities"] = case.expected_entities
                if case.expected_tools:
                    data["expected_tools"] = case.expected_tools
                
                f.write(json.dumps(data) + "\n")


class ModelEvaluator:
    """Evaluates fine-tuned models on SRE benchmarks.
    
    Example:
        config = EvaluationConfig(
            model_path=Path("./fine_tuned_model"),
            eval_types=[EvaluationType.ROOT_CAUSE, EvaluationType.TOOL_USE],
        )
        
        evaluator = ModelEvaluator(config)
        
        # Run evaluation
        results = evaluator.evaluate(benchmark_suite)
        
        # Compare with base model
        comparison = evaluator.compare_with_base(benchmark_suite)
        
        # Generate report
        evaluator.generate_report(results)
    """
    
    def __init__(self, config: EvaluationConfig):
        """Initialize the evaluator.
        
        Args:
            config: Evaluation configuration
        """
        self.config = config
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.model = None
        self.tokenizer = None
        self.base_model = None
    
    def load_model(self) -> None:
        """Load the model for evaluation."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
        except ImportError:
            raise ImportError("Evaluation requires: pip install transformers torch")
        
        logger.info(f"Loading model from {self.config.model_path}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.config.model_path,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        self.model.eval()
        
        # Load base model for comparison if specified
        if self.config.base_model:
            logger.info(f"Loading base model {self.config.base_model}")
            self.base_model = AutoModelForCausalLM.from_pretrained(
                self.config.base_model,
                torch_dtype=torch.bfloat16,
                device_map="auto",
            )
            self.base_model.eval()
    
    def evaluate(
        self,
        benchmark: BenchmarkSuite,
        eval_types: Optional[list[EvaluationType]] = None,
    ) -> list[EvaluationResult]:
        """Run evaluation on a benchmark suite.
        
        Args:
            benchmark: Benchmark suite to evaluate
            eval_types: Evaluation types (uses config default if not specified)
            
        Returns:
            List of evaluation results
        """
        if self.model is None:
            self.load_model()
        
        eval_types = eval_types or self.config.eval_types
        results = []
        
        for eval_type in eval_types:
            logger.info(f"Running {eval_type.value} evaluation...")
            
            if eval_type == EvaluationType.PERPLEXITY:
                result = self._eval_perplexity(benchmark)
            elif eval_type == EvaluationType.GENERATION:
                result = self._eval_generation(benchmark)
            elif eval_type == EvaluationType.ROOT_CAUSE:
                result = self._eval_root_cause(benchmark)
            elif eval_type == EvaluationType.TOOL_USE:
                result = self._eval_tool_use(benchmark)
            elif eval_type == EvaluationType.REASONING:
                result = self._eval_reasoning(benchmark)
            else:
                logger.warning(f"Unsupported evaluation type: {eval_type}")
                continue
            
            results.append(result)
            logger.info(f"{eval_type.value}: score={result.score:.4f}")
        
        # Save results
        self._save_results(results, benchmark.name)
        
        return results
    
    def _eval_perplexity(self, benchmark: BenchmarkSuite) -> EvaluationResult:
        """Evaluate perplexity on benchmark examples."""
        import torch
        
        total_loss = 0.0
        total_tokens = 0
        samples = []
        
        cases = benchmark.cases
        if self.config.max_eval_samples:
            cases = cases[:self.config.max_eval_samples]
        
        for case in cases:
            # Tokenize
            full_text = f"{case.input}\n{case.expected_output}"
            encoding = self.tokenizer(
                full_text,
                return_tensors="pt",
                truncation=True,
                max_length=2048,
            )
            
            input_ids = encoding["input_ids"].to(self.model.device)
            
            with torch.no_grad():
                outputs = self.model(input_ids, labels=input_ids)
                loss = outputs.loss.item()
            
            num_tokens = input_ids.shape[1]
            total_loss += loss * num_tokens
            total_tokens += num_tokens
            
            samples.append({
                "id": case.id,
                "loss": loss,
                "perplexity": 2 ** loss,
            })
        
        avg_loss = total_loss / total_tokens
        perplexity = 2 ** avg_loss
        
        return EvaluationResult(
            eval_type=EvaluationType.PERPLEXITY,
            score=perplexity,  # Lower is better
            metrics={
                "perplexity": perplexity,
                "loss": avg_loss,
                "total_tokens": total_tokens,
            },
            samples=samples,
        )
    
    def _eval_generation(self, benchmark: BenchmarkSuite) -> EvaluationResult:
        """Evaluate generation quality using multiple metrics."""
        samples = []
        bleu_scores = []
        rouge_scores = []
        exact_matches = 0
        
        cases = benchmark.cases
        if self.config.max_eval_samples:
            cases = cases[:self.config.max_eval_samples]
        
        for case in cases:
            # Generate response
            generated = self._generate(case.input)
            
            # Calculate metrics
            bleu = self._calculate_bleu(generated, case.expected_output)
            rouge = self._calculate_rouge(generated, case.expected_output)
            exact = int(self._normalize_text(generated) == self._normalize_text(case.expected_output))
            
            bleu_scores.append(bleu)
            rouge_scores.append(rouge)
            exact_matches += exact
            
            samples.append({
                "id": case.id,
                "input": case.input[:200],
                "expected": case.expected_output[:200],
                "generated": generated[:200],
                "bleu": bleu,
                "rouge": rouge,
                "exact_match": exact,
            })
        
        avg_bleu = sum(bleu_scores) / len(bleu_scores) if bleu_scores else 0
        avg_rouge = sum(rouge_scores) / len(rouge_scores) if rouge_scores else 0
        exact_match_rate = exact_matches / len(cases) if cases else 0
        
        # Combined score (weighted average)
        score = 0.4 * avg_bleu + 0.4 * avg_rouge + 0.2 * exact_match_rate
        
        return EvaluationResult(
            eval_type=EvaluationType.GENERATION,
            score=score,
            metrics={
                "bleu": avg_bleu,
                "rouge": avg_rouge,
                "exact_match_rate": exact_match_rate,
                "num_samples": len(cases),
            },
            samples=samples,
        )
    
    def _eval_root_cause(self, benchmark: BenchmarkSuite) -> EvaluationResult:
        """Evaluate root cause identification accuracy."""
        # Filter to root cause cases
        cases = [c for c in benchmark.cases if "root_cause" in c.tags or c.category == "root_cause"]
        if not cases:
            cases = benchmark.cases[:50]  # Use subset if no specific cases
        
        if self.config.max_eval_samples:
            cases = cases[:self.config.max_eval_samples]
        
        samples = []
        correct = 0
        partially_correct = 0
        
        for case in cases:
            generated = self._generate(case.input)
            
            # Check for key concepts in the root cause
            expected_concepts = self._extract_key_concepts(case.expected_output)
            generated_concepts = self._extract_key_concepts(generated)
            
            overlap = len(expected_concepts & generated_concepts)
            precision = overlap / len(generated_concepts) if generated_concepts else 0
            recall = overlap / len(expected_concepts) if expected_concepts else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            
            is_correct = f1 >= 0.7
            is_partial = f1 >= 0.3 and not is_correct
            
            if is_correct:
                correct += 1
            elif is_partial:
                partially_correct += 1
            
            samples.append({
                "id": case.id,
                "input": case.input[:200],
                "expected": case.expected_output[:200],
                "generated": generated[:200],
                "expected_concepts": list(expected_concepts),
                "generated_concepts": list(generated_concepts),
                "f1": f1,
                "correct": is_correct,
            })
        
        accuracy = correct / len(cases) if cases else 0
        partial_accuracy = (correct + partially_correct) / len(cases) if cases else 0
        
        return EvaluationResult(
            eval_type=EvaluationType.ROOT_CAUSE,
            score=accuracy,
            metrics={
                "accuracy": accuracy,
                "partial_accuracy": partial_accuracy,
                "correct": correct,
                "partially_correct": partially_correct,
                "total": len(cases),
            },
            samples=samples,
        )
    
    def _eval_tool_use(self, benchmark: BenchmarkSuite) -> EvaluationResult:
        """Evaluate tool selection and usage accuracy."""
        # Filter to tool use cases
        cases = [c for c in benchmark.cases if c.expected_tools]
        if not cases:
            logger.warning("No tool use cases found in benchmark")
            return EvaluationResult(
                eval_type=EvaluationType.TOOL_USE,
                score=0.0,
                metrics={"error": "No tool use cases found"},
                samples=[],
            )
        
        if self.config.max_eval_samples:
            cases = cases[:self.config.max_eval_samples]
        
        samples = []
        correct_tools = 0
        total_expected = 0
        
        for case in cases:
            generated = self._generate(case.input)
            
            # Extract tool references from generated text
            detected_tools = self._extract_tool_references(generated)
            expected = set(case.expected_tools or [])
            
            overlap = len(detected_tools & expected)
            correct_tools += overlap
            total_expected += len(expected)
            
            precision = overlap / len(detected_tools) if detected_tools else 0
            recall = overlap / len(expected) if expected else 0
            
            samples.append({
                "id": case.id,
                "expected_tools": list(expected),
                "detected_tools": list(detected_tools),
                "precision": precision,
                "recall": recall,
            })
        
        tool_recall = correct_tools / total_expected if total_expected > 0 else 0
        
        return EvaluationResult(
            eval_type=EvaluationType.TOOL_USE,
            score=tool_recall,
            metrics={
                "tool_recall": tool_recall,
                "correct_tools": correct_tools,
                "total_expected": total_expected,
            },
            samples=samples,
        )
    
    def _eval_reasoning(self, benchmark: BenchmarkSuite) -> EvaluationResult:
        """Evaluate multi-step reasoning quality."""
        cases = benchmark.cases
        if self.config.max_eval_samples:
            cases = cases[:self.config.max_eval_samples]
        
        samples = []
        reasoning_scores = []
        
        for case in cases:
            generated = self._generate(case.input)
            
            # Analyze reasoning structure
            has_steps = bool(re.search(r"(step\s*\d|first|then|next|finally)", generated, re.I))
            has_evidence = bool(re.search(r"(because|due to|since|shows that|indicates)", generated, re.I))
            has_conclusion = bool(re.search(r"(therefore|thus|conclusion|root cause|result)", generated, re.I))
            
            # Check logical structure
            score = (
                0.3 * int(has_steps) +
                0.4 * int(has_evidence) +
                0.3 * int(has_conclusion)
            )
            
            reasoning_scores.append(score)
            
            samples.append({
                "id": case.id,
                "has_steps": has_steps,
                "has_evidence": has_evidence,
                "has_conclusion": has_conclusion,
                "score": score,
            })
        
        avg_score = sum(reasoning_scores) / len(reasoning_scores) if reasoning_scores else 0
        
        return EvaluationResult(
            eval_type=EvaluationType.REASONING,
            score=avg_score,
            metrics={
                "avg_reasoning_score": avg_score,
                "with_steps_pct": sum(1 for s in samples if s["has_steps"]) / len(samples) if samples else 0,
                "with_evidence_pct": sum(1 for s in samples if s["has_evidence"]) / len(samples) if samples else 0,
                "with_conclusion_pct": sum(1 for s in samples if s["has_conclusion"]) / len(samples) if samples else 0,
            },
            samples=samples,
        )
    
    def _generate(self, prompt: str) -> str:
        """Generate response from the model."""
        import torch
        
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=2048 - self.config.max_new_tokens,
        )
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.config.max_new_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                do_sample=self.config.temperature > 0,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        
        # Decode only the generated part
        generated_ids = outputs[0][inputs["input_ids"].shape[1]:]
        generated_text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        
        return generated_text.strip()
    
    def _calculate_bleu(self, generated: str, reference: str) -> float:
        """Calculate BLEU score."""
        try:
            from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
            
            gen_tokens = generated.lower().split()
            ref_tokens = reference.lower().split()
            
            smoothing = SmoothingFunction().method1
            return sentence_bleu([ref_tokens], gen_tokens, smoothing_function=smoothing)
        except ImportError:
            # Simple fallback
            gen_set = set(generated.lower().split())
            ref_set = set(reference.lower().split())
            overlap = len(gen_set & ref_set)
            return overlap / len(ref_set) if ref_set else 0
    
    def _calculate_rouge(self, generated: str, reference: str) -> float:
        """Calculate ROUGE-L score."""
        gen_tokens = generated.lower().split()
        ref_tokens = reference.lower().split()
        
        # LCS (Longest Common Subsequence)
        def lcs_length(a: list, b: list) -> int:
            m, n = len(a), len(b)
            dp = [[0] * (n + 1) for _ in range(m + 1)]
            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    if a[i-1] == b[j-1]:
                        dp[i][j] = dp[i-1][j-1] + 1
                    else:
                        dp[i][j] = max(dp[i-1][j], dp[i][j-1])
            return dp[m][n]
        
        lcs = lcs_length(gen_tokens, ref_tokens)
        precision = lcs / len(gen_tokens) if gen_tokens else 0
        recall = lcs / len(ref_tokens) if ref_tokens else 0
        
        if precision + recall > 0:
            return 2 * precision * recall / (precision + recall)
        return 0
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        text = text.lower()
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
    
    def _extract_key_concepts(self, text: str) -> set[str]:
        """Extract key concepts from text."""
        # Simple keyword extraction
        text = text.lower()
        
        # Common SRE terms
        sre_terms = {
            "cpu", "memory", "disk", "network", "latency", "timeout",
            "error", "crash", "oom", "restart", "connection", "database",
            "cache", "queue", "deadlock", "leak", "overflow", "pod",
            "deployment", "service", "node", "container", "rate limit",
        }
        
        found = set()
        words = set(text.split())
        
        for term in sre_terms:
            if term in text or term in words:
                found.add(term)
        
        # Also extract quoted terms
        quoted = re.findall(r'"([^"]+)"', text)
        found.update(q.lower() for q in quoted)
        
        return found
    
    def _extract_tool_references(self, text: str) -> set[str]:
        """Extract tool references from generated text."""
        text = text.lower()
        
        # Common SRE tools
        tools = {
            "kubectl", "prometheus", "grafana", "datadog", "pagerduty",
            "aws", "gcp", "k8s", "docker", "helm", "terraform",
            "splunk", "elasticsearch", "kibana", "newrelic", "cloudwatch",
        }
        
        found = set()
        for tool in tools:
            if tool in text:
                found.add(tool)
        
        # Also look for function calls
        func_calls = re.findall(r"(\w+)\s*\(", text)
        found.update(f.lower() for f in func_calls if len(f) > 2)
        
        return found
    
    def compare_with_base(
        self,
        benchmark: BenchmarkSuite,
    ) -> dict[str, Any]:
        """Compare fine-tuned model with base model.
        
        Returns:
            Comparison results showing improvement
        """
        if not self.config.base_model:
            raise ValueError("No base model specified for comparison")
        
        if self.model is None:
            self.load_model()
        
        # Evaluate fine-tuned model
        logger.info("Evaluating fine-tuned model...")
        finetuned_results = self.evaluate(benchmark)
        
        # Temporarily swap models
        finetuned_model = self.model
        self.model = self.base_model
        
        # Evaluate base model
        logger.info("Evaluating base model...")
        base_results = self.evaluate(benchmark)
        
        # Restore fine-tuned model
        self.model = finetuned_model
        
        # Compare results
        comparison = {
            "benchmark": benchmark.name,
            "fine_tuned_model": str(self.config.model_path),
            "base_model": self.config.base_model,
            "results": [],
        }
        
        for ft_result, base_result in zip(finetuned_results, base_results):
            improvement = ft_result.score - base_result.score
            improvement_pct = (improvement / base_result.score * 100) if base_result.score != 0 else 0
            
            comparison["results"].append({
                "eval_type": ft_result.eval_type.value,
                "base_score": base_result.score,
                "finetuned_score": ft_result.score,
                "improvement": improvement,
                "improvement_pct": improvement_pct,
            })
        
        # Save comparison
        comparison_path = self.config.output_dir / f"comparison_{benchmark.name}.json"
        with open(comparison_path, "w") as f:
            json.dump(comparison, f, indent=2)
        
        return comparison
    
    def _save_results(
        self,
        results: list[EvaluationResult],
        benchmark_name: str,
    ) -> None:
        """Save evaluation results to disk."""
        # Save summary
        summary = {
            "benchmark": benchmark_name,
            "model": str(self.config.model_path),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": [r.to_dict() for r in results],
        }
        
        summary_path = self.config.output_dir / f"eval_{benchmark_name}.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Saved evaluation results to {summary_path}")
        
        # Save detailed predictions if configured
        if self.config.save_predictions:
            for result in results:
                if result.samples:
                    pred_path = self.config.output_dir / f"predictions_{benchmark_name}_{result.eval_type.value}.jsonl"
                    with open(pred_path, "w") as f:
                        for sample in result.samples:
                            f.write(json.dumps(sample) + "\n")
    
    def generate_report(
        self,
        results: list[EvaluationResult],
        output_format: str = "markdown",
    ) -> str:
        """Generate an evaluation report.
        
        Args:
            results: Evaluation results
            output_format: Report format ("markdown" or "text")
            
        Returns:
            Report content
        """
        lines = []
        
        if output_format == "markdown":
            lines.append("# Model Evaluation Report")
            lines.append("")
            lines.append(f"**Model:** `{self.config.model_path}`")
            lines.append(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
            lines.append("")
            lines.append("## Summary")
            lines.append("")
            lines.append("| Evaluation Type | Score | Details |")
            lines.append("|----------------|-------|---------|")
            
            for result in results:
                details = ", ".join(f"{k}={v:.3f}" for k, v in list(result.metrics.items())[:3])
                lines.append(f"| {result.eval_type.value} | {result.score:.4f} | {details} |")
            
            lines.append("")
            lines.append("## Detailed Results")
            
            for result in results:
                lines.append("")
                lines.append(f"### {result.eval_type.value.replace('_', ' ').title()}")
                lines.append("")
                lines.append("**Metrics:**")
                for k, v in result.metrics.items():
                    if isinstance(v, float):
                        lines.append(f"- {k}: {v:.4f}")
                    else:
                        lines.append(f"- {k}: {v}")
        else:
            # Plain text format
            lines.append("Model Evaluation Report")
            lines.append("=" * 50)
            lines.append(f"Model: {self.config.model_path}")
            lines.append(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
            lines.append("")
            
            for result in results:
                lines.append(f"{result.eval_type.value}: {result.score:.4f}")
                for k, v in result.metrics.items():
                    if isinstance(v, float):
                        lines.append(f"  - {k}: {v:.4f}")
                    else:
                        lines.append(f"  - {k}: {v}")
                lines.append("")
        
        report = "\n".join(lines)
        
        # Save report
        ext = ".md" if output_format == "markdown" else ".txt"
        report_path = self.config.output_dir / f"report{ext}"
        with open(report_path, "w") as f:
            f.write(report)
        
        logger.info(f"Generated report at {report_path}")
        return report


def create_sre_benchmark() -> BenchmarkSuite:
    """Create a standard SRE benchmark suite.
    
    Returns a benchmark suite with common SRE scenarios for evaluation.
    """
    cases = [
        BenchmarkCase(
            id="rca_001",
            category="root_cause",
            input="""Alert: High CPU usage on api-server pods
Severity: Warning
Service: api-server
Environment: production

Current CPU usage is 85%, threshold is 80%.
Recent changes: New deployment 2 hours ago.
Error logs show increased request latency.

What is the root cause?""",
            expected_output="""Based on the investigation:
1. High CPU correlates with the new deployment 2 hours ago
2. Increased request latency suggests processing inefficiency
3. The new code may have introduced a CPU-intensive operation

Root cause: The recent deployment likely introduced inefficient code or 
increased computational complexity, causing elevated CPU usage.""",
            difficulty="medium",
            tags=["root_cause", "cpu", "deployment"],
        ),
        BenchmarkCase(
            id="rca_002",
            category="root_cause",
            input="""Alert: OOMKilled pods in payment-service
Severity: Critical
Service: payment-service
Environment: production

3 pods have been OOMKilled in the last hour.
Memory usage spiked from 60% to 100% before each kill.
No recent deployments.

Investigate and identify the root cause.""",
            expected_output="""Investigation findings:
1. OOMKilled indicates pods exceeded memory limits
2. No recent deployments rules out code changes
3. Memory spike pattern suggests a memory leak or 
   sudden increase in load

Root cause: Likely a memory leak in the payment-service that 
accumulates over time, or an unexpected traffic spike causing 
memory pressure. Check for unbounded caches or connection pools.""",
            difficulty="medium",
            tags=["root_cause", "memory", "oom"],
        ),
        BenchmarkCase(
            id="tool_001",
            category="tool_use",
            input="""A Kubernetes deployment is failing to roll out.
The pods are stuck in Pending state.
What tools should I use to investigate?""",
            expected_output="""To investigate pending pods, use these tools:
1. kubectl describe pod <pod-name> - Check events and conditions
2. kubectl get events - View cluster events
3. kubectl describe nodes - Check node capacity and conditions
4. kubectl logs - Check init container logs if applicable""",
            difficulty="easy",
            expected_tools=["kubectl"],
            tags=["tool_use", "kubernetes"],
        ),
        BenchmarkCase(
            id="reason_001",
            category="reasoning",
            input="""Service A depends on Service B.
Service B has 50% error rate.
Service A is reporting 503 errors.
Connection timeouts to database are increasing.

Walk through the investigation step by step.""",
            expected_output="""Step 1: Start with the symptoms
- Service A is failing with 503 errors
- This indicates upstream failures

Step 2: Check dependencies
- Service A depends on Service B
- Service B has 50% error rate, which explains A's failures

Step 3: Investigate Service B
- Database connection timeouts are increasing
- This suggests the database is the root cause

Step 4: Conclusion
Therefore, the cascading failure originates from database issues:
Database timeouts -> Service B errors -> Service A 503 errors

Root cause: Database connection issues causing cascade failure.""",
            difficulty="hard",
            tags=["reasoning", "cascade", "dependencies"],
        ),
    ]
    
    return BenchmarkSuite(
        name="autosre_standard",
        description="Standard AutoSRE evaluation benchmark for SRE tasks",
        cases=cases,
    )
