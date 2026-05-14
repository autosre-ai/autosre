"""ML Pipeline utilities for AutoSRE."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional, List, Dict, Callable, Generic, TypeVar
from enum import Enum
import time
import traceback

from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id


class StepStatus(str, Enum):
    """Status of a pipeline step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStep(BaseModel):
    """A step in a ML pipeline."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    step_id: str = Field(default_factory=generate_id)
    name: str = Field(..., min_length=1)
    description: str = Field(default="")
    
    # Status
    status: StepStatus = Field(default=StepStatus.PENDING)
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = Field(default=0.0, ge=0.0)
    
    # Results
    output: Any = None
    error: Optional[str] = None
    error_traceback: Optional[str] = None
    
    # Metrics
    metrics: dict[str, float] = Field(default_factory=dict)
    
    # Dependencies
    depends_on: list[str] = Field(default_factory=list)
    
    # Configuration
    config: dict[str, Any] = Field(default_factory=dict)
    
    def mark_started(self) -> None:
        """Mark step as started."""
        self.status = StepStatus.RUNNING
        self.started_at = utc_now()
    
    def mark_completed(self, output: Any = None, metrics: Optional[dict[str, float]] = None) -> None:
        """Mark step as completed."""
        self.status = StepStatus.COMPLETED
        self.completed_at = utc_now()
        self.output = output
        if metrics:
            self.metrics.update(metrics)
        if self.started_at:
            self.duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000
    
    def mark_failed(self, error: str, traceback_str: Optional[str] = None) -> None:
        """Mark step as failed."""
        self.status = StepStatus.FAILED
        self.completed_at = utc_now()
        self.error = error
        self.error_traceback = traceback_str
        if self.started_at:
            self.duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000
    
    def mark_skipped(self, reason: str = "") -> None:
        """Mark step as skipped."""
        self.status = StepStatus.SKIPPED
        self.completed_at = utc_now()
        if reason:
            self.error = reason


class PipelineResult(BaseModel):
    """Result of a pipeline execution."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    pipeline_id: str = Field(default_factory=generate_id)
    pipeline_name: str = Field(default="")
    
    # Status
    status: StepStatus = Field(default=StepStatus.PENDING)
    
    # Steps
    steps: list[PipelineStep] = Field(default_factory=list)
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_duration_ms: float = Field(default=0.0, ge=0.0)
    
    # Final output
    final_output: Any = None
    
    # Aggregate metrics
    metrics: dict[str, float] = Field(default_factory=dict)
    
    # Errors
    errors: list[str] = Field(default_factory=list)
    
    @property
    def success(self) -> bool:
        """Check if pipeline succeeded."""
        return self.status == StepStatus.COMPLETED
    
    @property
    def num_steps(self) -> int:
        """Get total number of steps."""
        return len(self.steps)
    
    @property
    def num_completed(self) -> int:
        """Get number of completed steps."""
        return sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
    
    @property
    def num_failed(self) -> int:
        """Get number of failed steps."""
        return sum(1 for s in self.steps if s.status == StepStatus.FAILED)
    
    def get_step(self, name: str) -> Optional[PipelineStep]:
        """Get step by name."""
        for step in self.steps:
            if step.name == name:
                return step
        return None


class PipelineConfig(BaseModel):
    """Configuration for a pipeline."""
    model_config = ConfigDict(validate_assignment=True)
    
    name: str = Field(default="pipeline")
    description: str = Field(default="")
    
    # Execution options
    continue_on_error: bool = Field(default=False)
    max_retries: int = Field(default=0, ge=0)
    retry_delay_ms: int = Field(default=1000, ge=0)
    timeout_ms: Optional[int] = None
    
    # Parallelization
    parallel_execution: bool = Field(default=False)
    max_workers: int = Field(default=4, ge=1)
    
    # Caching
    cache_intermediate: bool = Field(default=False)
    cache_dir: Optional[str] = None
    
    # Logging
    log_level: str = Field(default="INFO")
    verbose: bool = Field(default=False)


InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class Pipeline(Generic[InputT, OutputT]):
    """ML Pipeline for chaining operations.
    
    Provides:
    - Step-by-step execution with timing and metrics
    - Error handling and retries
    - Dependency management between steps
    - Caching of intermediate results
    """
    
    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
    ):
        """Initialize the pipeline.
        
        Args:
            config: Pipeline configuration
        """
        self.config = config or PipelineConfig()
        self._steps: list[tuple[str, Callable, dict]] = []
        self._step_dependencies: dict[str, list[str]] = {}
    
    def add_step(
        self,
        name: str,
        func: Callable,
        depends_on: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> "Pipeline":
        """Add a step to the pipeline.
        
        Args:
            name: Step name
            func: Function to execute
            depends_on: List of step names this depends on
            **kwargs: Additional configuration
            
        Returns:
            Self for chaining
        """
        self._steps.append((name, func, kwargs))
        if depends_on:
            self._step_dependencies[name] = depends_on
        return self
    
    def _get_execution_order(self) -> list[str]:
        """Determine step execution order based on dependencies.
        
        Returns:
            Ordered list of step names
        """
        # Simple topological sort
        visited = set()
        order = []
        
        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            
            for dep in self._step_dependencies.get(name, []):
                visit(dep)
            
            order.append(name)
        
        for name, _, _ in self._steps:
            visit(name)
        
        return order
    
    def run(
        self,
        input_data: InputT,
        context: Optional[dict[str, Any]] = None,
    ) -> PipelineResult:
        """Execute the pipeline.
        
        Args:
            input_data: Initial input data
            context: Additional context passed to all steps
            
        Returns:
            Pipeline execution result
        """
        result = PipelineResult(
            pipeline_name=self.config.name,
            started_at=utc_now(),
        )
        result.status = StepStatus.RUNNING
        
        context = context or {}
        step_outputs: dict[str, Any] = {"input": input_data}
        
        # Create step objects
        step_map = {}
        for name, func, kwargs in self._steps:
            step = PipelineStep(
                name=name,
                depends_on=self._step_dependencies.get(name, []),
                config=kwargs,
            )
            result.steps.append(step)
            step_map[name] = step
        
        # Execute in order
        execution_order = self._get_execution_order()
        
        for step_name in execution_order:
            step = step_map.get(step_name)
            if not step:
                continue
            
            # Find the step function
            step_func = None
            step_kwargs = {}
            for name, func, kwargs in self._steps:
                if name == step_name:
                    step_func = func
                    step_kwargs = kwargs
                    break
            
            if step_func is None:
                continue
            
            # Check dependencies
            skip = False
            for dep in step.depends_on:
                dep_step = step_map.get(dep)
                if dep_step and dep_step.status != StepStatus.COMPLETED:
                    step.mark_skipped(f"Dependency {dep} not completed")
                    skip = True
                    break
            
            if skip:
                continue
            
            # Execute step with retries
            retries = 0
            while retries <= self.config.max_retries:
                step.mark_started()
                
                try:
                    # Prepare input
                    if step.depends_on:
                        step_input = {
                            dep: step_outputs.get(dep)
                            for dep in step.depends_on
                        }
                    else:
                        step_input = step_outputs.get("input", input_data)
                    
                    # Call function
                    output = step_func(step_input, context=context, **step_kwargs)
                    
                    # Store output
                    step_outputs[step_name] = output
                    step.mark_completed(output=output)
                    break
                    
                except Exception as e:
                    retries += 1
                    if retries > self.config.max_retries:
                        step.mark_failed(
                            error=str(e),
                            traceback_str=traceback.format_exc(),
                        )
                        result.errors.append(f"{step_name}: {str(e)}")
                        
                        if not self.config.continue_on_error:
                            result.status = StepStatus.FAILED
                            result.completed_at = utc_now()
                            result.total_duration_ms = (
                                result.completed_at - result.started_at
                            ).total_seconds() * 1000
                            return result
                    else:
                        time.sleep(self.config.retry_delay_ms / 1000)
        
        # Finalize
        result.completed_at = utc_now()
        result.total_duration_ms = (
            result.completed_at - result.started_at
        ).total_seconds() * 1000
        
        # Check overall status
        if result.num_failed > 0:
            result.status = StepStatus.FAILED if not self.config.continue_on_error else StepStatus.COMPLETED
        else:
            result.status = StepStatus.COMPLETED
        
        # Set final output from last step
        if execution_order:
            last_step = execution_order[-1]
            result.final_output = step_outputs.get(last_step)
        
        # Aggregate metrics
        for step in result.steps:
            for metric_name, value in step.metrics.items():
                result.metrics[f"{step.name}.{metric_name}"] = value
        
        return result
    
    def __repr__(self) -> str:
        step_names = [name for name, _, _ in self._steps]
        return f"Pipeline(name='{self.config.name}', steps={step_names})"


class TransformStep:
    """A reusable transform step for pipelines."""
    
    def __init__(
        self,
        name: str,
        transform_fn: Callable[[Any], Any],
        description: str = "",
    ):
        """Initialize the transform step.
        
        Args:
            name: Step name
            transform_fn: Transform function
            description: Step description
        """
        self.name = name
        self.transform_fn = transform_fn
        self.description = description
    
    def __call__(self, data: Any, context: Optional[dict] = None, **kwargs: Any) -> Any:
        """Execute the transform."""
        return self.transform_fn(data)


class FitTransformStep:
    """A step that fits on data and then transforms it."""
    
    def __init__(
        self,
        name: str,
        fit_fn: Callable[[Any], Any],
        transform_fn: Callable[[Any, Any], Any],
        description: str = "",
    ):
        """Initialize the fit-transform step.
        
        Args:
            name: Step name
            fit_fn: Function to fit on data
            transform_fn: Function to transform data
            description: Step description
        """
        self.name = name
        self.fit_fn = fit_fn
        self.transform_fn = transform_fn
        self.description = description
        self._fitted_state: Any = None
    
    def fit(self, data: Any) -> "FitTransformStep":
        """Fit on data."""
        self._fitted_state = self.fit_fn(data)
        return self
    
    def transform(self, data: Any) -> Any:
        """Transform data using fitted state."""
        if self._fitted_state is None:
            raise ValueError("Step not fitted. Call fit() first.")
        return self.transform_fn(data, self._fitted_state)
    
    def fit_transform(self, data: Any) -> Any:
        """Fit and transform in one step."""
        self.fit(data)
        return self.transform(data)
    
    def __call__(
        self,
        data: Any,
        context: Optional[dict] = None,
        mode: str = "fit_transform",
        **kwargs: Any,
    ) -> Any:
        """Execute the step."""
        if mode == "fit":
            self.fit(data)
            return self._fitted_state
        elif mode == "transform":
            return self.transform(data)
        else:  # fit_transform
            return self.fit_transform(data)


class PipelineBuilder:
    """Builder for creating pipelines with a fluent API."""
    
    def __init__(self, name: str = "pipeline"):
        """Initialize the builder.
        
        Args:
            name: Pipeline name
        """
        self._config = PipelineConfig(name=name)
        self._steps: list[tuple[str, Callable, list[str], dict]] = []
    
    def with_config(self, **kwargs: Any) -> "PipelineBuilder":
        """Set configuration options.
        
        Args:
            **kwargs: Configuration options
            
        Returns:
            Self for chaining
        """
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        return self
    
    def add(
        self,
        name: str,
        func: Callable,
        depends_on: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> "PipelineBuilder":
        """Add a step.
        
        Args:
            name: Step name
            func: Step function
            depends_on: Dependencies
            **kwargs: Step configuration
            
        Returns:
            Self for chaining
        """
        self._steps.append((name, func, depends_on or [], kwargs))
        return self
    
    def build(self) -> Pipeline:
        """Build the pipeline.
        
        Returns:
            Configured pipeline
        """
        pipeline = Pipeline(config=self._config)
        
        for name, func, depends_on, kwargs in self._steps:
            pipeline.add_step(name, func, depends_on=depends_on if depends_on else None, **kwargs)
        
        return pipeline


# Convenience functions for common pipeline patterns
def preprocess_pipeline(
    handle_missing: bool = True,
    handle_outliers: bool = True,
    scale: bool = True,
) -> Pipeline:
    """Create a standard preprocessing pipeline.
    
    Args:
        handle_missing: Handle missing values
        handle_outliers: Handle outliers
        scale: Scale features
        
    Returns:
        Preprocessing pipeline
    """
    from autosre.ml.common.preprocessing import DataPreprocessor, MissingValueHandler, OutlierHandler
    from autosre.ml.common.features import FeatureScaler
    
    import numpy as np
    
    builder = PipelineBuilder("preprocessing")
    
    if handle_missing:
        def missing_step(data: Any, **kwargs: Any) -> Any:
            handler = MissingValueHandler()
            return handler.fit_transform(np.asarray(data))
        builder.add("handle_missing", missing_step)
    
    if handle_outliers:
        def outlier_step(data: Any, **kwargs: Any) -> Any:
            handler = OutlierHandler()
            return handler.fit_transform(np.asarray(data))
        deps = ["handle_missing"] if handle_missing else None
        builder.add("handle_outliers", outlier_step, depends_on=deps)
    
    if scale:
        def scale_step(data: Any, **kwargs: Any) -> Any:
            scaler = FeatureScaler()
            return scaler.fit_transform(np.asarray(data))
        deps = []
        if handle_outliers:
            deps.append("handle_outliers")
        elif handle_missing:
            deps.append("handle_missing")
        builder.add("scale", scale_step, depends_on=deps if deps else None)
    
    return builder.build()
