"""Model registry for storing and versioning ML models."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, List
import json
import hashlib
import shutil

from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now
from autosre.ml.common.base import (
    BaseMLModel,
    ModelMetadata,
    ModelStatus,
    ModelVersion,
    generate_model_id,
)


class ModelFilter(BaseModel):
    """Filter criteria for querying models."""
    model_config = ConfigDict(validate_assignment=True)
    
    model_type: Optional[str] = None
    status: Optional[ModelStatus] = None
    owner: Optional[str] = None
    team: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    name_contains: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    min_metric: Optional[dict[str, float]] = None
    max_metric: Optional[dict[str, float]] = None


class ModelEntry(BaseModel):
    """An entry in the model registry."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    model_id: str = Field(...)
    metadata: ModelMetadata
    artifact_paths: dict[str, str] = Field(default_factory=dict)  # version_id -> path
    
    # Deployment info
    production_version: Optional[str] = None
    staging_version: Optional[str] = None
    
    # Checksums
    checksums: dict[str, str] = Field(default_factory=dict)  # version_id -> checksum
    
    # Access control
    read_access: list[str] = Field(default_factory=list)
    write_access: list[str] = Field(default_factory=list)
    
    # Timestamps
    registered_at: datetime = Field(default_factory=utc_now)
    last_accessed_at: Optional[datetime] = None


class ModelRegistry:
    """Registry for managing ML models.
    
    Provides:
    - Model versioning and storage
    - Model search and filtering
    - Deployment tracking
    - Model lifecycle management
    """
    
    def __init__(
        self,
        storage_path: str = "./model_registry",
        backend: str = "filesystem",
    ):
        """Initialize the model registry.
        
        Args:
            storage_path: Path to store models and metadata
            backend: Storage backend ('filesystem', 'gcs', 's3')
        """
        self.storage_path = Path(storage_path)
        self.backend = backend
        self._entries: dict[str, ModelEntry] = {}
        self._index_path = self.storage_path / "index.json"
        
        # Initialize storage
        self._init_storage()
    
    def _init_storage(self) -> None:
        """Initialize storage backend."""
        if self.backend == "filesystem":
            self.storage_path.mkdir(parents=True, exist_ok=True)
            if self._index_path.exists():
                self._load_index()
    
    def _load_index(self) -> None:
        """Load registry index from disk."""
        try:
            with open(self._index_path) as f:
                data = json.load(f)
                for model_id, entry_data in data.items():
                    self._entries[model_id] = ModelEntry(**entry_data)
        except Exception:
            self._entries = {}
    
    def _save_index(self) -> None:
        """Save registry index to disk."""
        data = {
            model_id: entry.model_dump(mode="json")
            for model_id, entry in self._entries.items()
        }
        with open(self._index_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    
    def _compute_checksum(self, path: Path) -> str:
        """Compute SHA256 checksum of a file or directory."""
        sha256 = hashlib.sha256()
        
        if path.is_file():
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
        elif path.is_dir():
            for file_path in sorted(path.rglob("*")):
                if file_path.is_file():
                    with open(file_path, "rb") as f:
                        for chunk in iter(lambda: f.read(8192), b""):
                            sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def register(
        self,
        model: BaseMLModel,
        description: str = "",
        tags: Optional[list[str]] = None,
    ) -> ModelEntry:
        """Register a new model in the registry.
        
        Args:
            model: Model to register
            description: Model description
            tags: Tags for the model
            
        Returns:
            Registry entry for the model
        """
        model_id = model.model_id
        
        if model_id in self._entries:
            raise ValueError(f"Model {model_id} already registered")
        
        # Update metadata
        if description:
            model.metadata.description = description
        if tags:
            model.metadata.tags = tags
        
        # Create entry
        entry = ModelEntry(
            model_id=model_id,
            metadata=model.metadata,
        )
        
        self._entries[model_id] = entry
        self._save_index()
        
        return entry
    
    def log_version(
        self,
        model_id: str,
        model: BaseMLModel,
        metrics: Optional[dict[str, float]] = None,
        description: str = "",
    ) -> ModelVersion:
        """Log a new version of a model.
        
        Args:
            model_id: ID of the registered model
            model: Trained model instance
            metrics: Evaluation metrics
            description: Version description
            
        Returns:
            New model version
        """
        if model_id not in self._entries:
            raise ValueError(f"Model {model_id} not found in registry")
        
        entry = self._entries[model_id]
        
        # Create version
        version_number = len(entry.metadata.versions) + 1
        version = ModelVersion(
            version_number=version_number,
            description=description,
            metrics=metrics or {},
        )
        
        # Save model artifacts
        artifact_dir = self.storage_path / model_id / version.version_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        model.save(str(artifact_dir))
        
        # Compute checksum
        checksum = self._compute_checksum(artifact_dir)
        entry.checksums[version.version_id] = checksum
        
        # Update artifact path
        version.artifact_path = str(artifact_dir)
        version.artifact_size_bytes = sum(
            f.stat().st_size for f in artifact_dir.rglob("*") if f.is_file()
        )
        
        entry.artifact_paths[version.version_id] = str(artifact_dir)
        entry.metadata.add_version(version)
        
        self._save_index()
        
        return version
    
    def get_model(
        self,
        model_id: str,
        version_id: Optional[str] = None,
    ) -> BaseMLModel:
        """Load a model from the registry.
        
        Args:
            model_id: Model ID
            version_id: Specific version (default: latest)
            
        Returns:
            Loaded model
        """
        if model_id not in self._entries:
            raise ValueError(f"Model {model_id} not found")
        
        entry = self._entries[model_id]
        
        if version_id is None:
            if entry.metadata.current_version is None:
                raise ValueError(f"No versions found for model {model_id}")
            version_id = entry.metadata.current_version.version_id
        
        if version_id not in entry.artifact_paths:
            raise ValueError(f"Version {version_id} not found for model {model_id}")
        
        artifact_path = entry.artifact_paths[version_id]
        
        # Verify checksum
        if version_id in entry.checksums:
            current_checksum = self._compute_checksum(Path(artifact_path))
            if current_checksum != entry.checksums[version_id]:
                raise ValueError(f"Model artifact checksum mismatch for {model_id}:{version_id}")
        
        # Update access time
        entry.last_accessed_at = utc_now()
        self._save_index()
        
        # Load model
        from autosre.ml.common.serialization import ModelSerializer
        serializer = ModelSerializer()
        return serializer.load(artifact_path)
    
    def get_metadata(self, model_id: str) -> ModelMetadata:
        """Get model metadata.
        
        Args:
            model_id: Model ID
            
        Returns:
            Model metadata
        """
        if model_id not in self._entries:
            raise ValueError(f"Model {model_id} not found")
        
        return self._entries[model_id].metadata
    
    def list_models(
        self,
        filter_by: Optional[ModelFilter] = None,
    ) -> list[ModelEntry]:
        """List models in the registry.
        
        Args:
            filter_by: Filter criteria
            
        Returns:
            List of matching model entries
        """
        entries = list(self._entries.values())
        
        if filter_by is None:
            return entries
        
        result = []
        for entry in entries:
            metadata = entry.metadata
            
            # Apply filters
            if filter_by.model_type and metadata.model_type != filter_by.model_type:
                continue
            if filter_by.status and metadata.status != filter_by.status:
                continue
            if filter_by.owner and metadata.owner != filter_by.owner:
                continue
            if filter_by.team and metadata.team != filter_by.team:
                continue
            if filter_by.tags and not all(t in metadata.tags for t in filter_by.tags):
                continue
            if filter_by.name_contains and filter_by.name_contains.lower() not in metadata.name.lower():
                continue
            if filter_by.created_after and metadata.created_at < filter_by.created_after:
                continue
            if filter_by.created_before and metadata.created_at > filter_by.created_before:
                continue
            
            # Metric filters
            if filter_by.min_metric and metadata.current_version:
                version_metrics = metadata.current_version.metrics
                if not all(
                    version_metrics.get(k, float("-inf")) >= v
                    for k, v in filter_by.min_metric.items()
                ):
                    continue
            
            if filter_by.max_metric and metadata.current_version:
                version_metrics = metadata.current_version.metrics
                if not all(
                    version_metrics.get(k, float("inf")) <= v
                    for k, v in filter_by.max_metric.items()
                ):
                    continue
            
            result.append(entry)
        
        return result
    
    def promote_to_production(
        self,
        model_id: str,
        version_id: Optional[str] = None,
    ) -> None:
        """Promote a model version to production.
        
        Args:
            model_id: Model ID
            version_id: Version to promote (default: latest)
        """
        if model_id not in self._entries:
            raise ValueError(f"Model {model_id} not found")
        
        entry = self._entries[model_id]
        
        if version_id is None:
            if entry.metadata.current_version is None:
                raise ValueError(f"No versions found for model {model_id}")
            version_id = entry.metadata.current_version.version_id
        
        # Move current production to staging
        if entry.production_version:
            entry.staging_version = entry.production_version
        
        entry.production_version = version_id
        entry.metadata.status = ModelStatus.DEPLOYED
        entry.metadata.last_deployed_at = utc_now()
        
        self._save_index()
    
    def promote_to_staging(
        self,
        model_id: str,
        version_id: Optional[str] = None,
    ) -> None:
        """Promote a model version to staging.
        
        Args:
            model_id: Model ID
            version_id: Version to promote (default: latest)
        """
        if model_id not in self._entries:
            raise ValueError(f"Model {model_id} not found")
        
        entry = self._entries[model_id]
        
        if version_id is None:
            if entry.metadata.current_version is None:
                raise ValueError(f"No versions found for model {model_id}")
            version_id = entry.metadata.current_version.version_id
        
        entry.staging_version = version_id
        entry.metadata.status = ModelStatus.VALIDATED
        
        self._save_index()
    
    def deprecate(self, model_id: str) -> None:
        """Deprecate a model.
        
        Args:
            model_id: Model ID
        """
        if model_id not in self._entries:
            raise ValueError(f"Model {model_id} not found")
        
        self._entries[model_id].metadata.status = ModelStatus.DEPRECATED
        self._save_index()
    
    def delete(
        self,
        model_id: str,
        delete_artifacts: bool = False,
    ) -> None:
        """Delete a model from the registry.
        
        Args:
            model_id: Model ID
            delete_artifacts: Also delete model artifacts
        """
        if model_id not in self._entries:
            raise ValueError(f"Model {model_id} not found")
        
        if delete_artifacts:
            model_dir = self.storage_path / model_id
            if model_dir.exists():
                shutil.rmtree(model_dir)
        
        del self._entries[model_id]
        self._save_index()
    
    def compare_versions(
        self,
        model_id: str,
        version_a: str,
        version_b: str,
    ) -> dict[str, Any]:
        """Compare two model versions.
        
        Args:
            model_id: Model ID
            version_a: First version ID
            version_b: Second version ID
            
        Returns:
            Comparison results
        """
        if model_id not in self._entries:
            raise ValueError(f"Model {model_id} not found")
        
        entry = self._entries[model_id]
        
        va = entry.metadata.get_version(version_a)
        vb = entry.metadata.get_version(version_b)
        
        if va is None:
            raise ValueError(f"Version {version_a} not found")
        if vb is None:
            raise ValueError(f"Version {version_b} not found")
        
        # Compare metrics
        all_metrics = set(va.metrics.keys()) | set(vb.metrics.keys())
        metric_comparison = {}
        
        for metric in all_metrics:
            val_a = va.metrics.get(metric)
            val_b = vb.metrics.get(metric)
            
            if val_a is not None and val_b is not None:
                diff = val_b - val_a
                pct_change = (diff / val_a * 100) if val_a != 0 else float("inf")
                metric_comparison[metric] = {
                    "version_a": val_a,
                    "version_b": val_b,
                    "difference": diff,
                    "percent_change": pct_change,
                }
            else:
                metric_comparison[metric] = {
                    "version_a": val_a,
                    "version_b": val_b,
                    "difference": None,
                    "percent_change": None,
                }
        
        return {
            "model_id": model_id,
            "version_a": {
                "version_id": version_a,
                "version_number": va.version_number,
                "created_at": va.created_at.isoformat(),
            },
            "version_b": {
                "version_id": version_b,
                "version_number": vb.version_number,
                "created_at": vb.created_at.isoformat(),
            },
            "metrics": metric_comparison,
        }
    
    def get_production_model(
        self,
        model_type: str,
    ) -> Optional[BaseMLModel]:
        """Get the production model for a given type.
        
        Args:
            model_type: Type of model to get
            
        Returns:
            Production model or None
        """
        for entry in self._entries.values():
            if (
                entry.metadata.model_type == model_type
                and entry.production_version is not None
            ):
                return self.get_model(
                    entry.model_id,
                    entry.production_version,
                )
        return None
    
    def __len__(self) -> int:
        return len(self._entries)
    
    def __contains__(self, model_id: str) -> bool:
        return model_id in self._entries
