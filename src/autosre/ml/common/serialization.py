"""Model serialization and persistence."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Type, Dict
import json
import pickle
import hashlib
import gzip

from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now


class SerializationFormat(str, Enum):
    """Format for model serialization."""
    PICKLE = "pickle"
    JOBLIB = "joblib"
    ONNX = "onnx"
    JSON = "json"
    SAFETENSORS = "safetensors"


class ModelArtifact(BaseModel):
    """Metadata for a model artifact."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    # Identification
    artifact_id: str = Field(default="")
    model_id: str = Field(default="")
    model_name: str = Field(default="")
    model_type: str = Field(default="")
    model_class: str = Field(default="")
    
    # Format
    format: SerializationFormat = Field(default=SerializationFormat.PICKLE)
    compressed: bool = Field(default=False)
    
    # Files
    main_file: str = Field(default="model.pkl")
    metadata_file: str = Field(default="metadata.json")
    config_file: str = Field(default="config.json")
    
    # Size
    size_bytes: int = Field(default=0, ge=0)
    compressed_size_bytes: Optional[int] = None
    
    # Integrity
    checksum: str = Field(default="")
    checksum_algorithm: str = Field(default="sha256")
    
    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    
    # Additional data
    extra_files: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class ModelSerializer:
    """Serialize and deserialize ML models."""
    
    def __init__(
        self,
        format: SerializationFormat = SerializationFormat.PICKLE,
        compress: bool = True,
        compression_level: int = 6,
    ):
        """Initialize the serializer.
        
        Args:
            format: Serialization format
            compress: Whether to compress artifacts
            compression_level: gzip compression level (1-9)
        """
        self.format = format
        self.compress = compress
        self.compression_level = compression_level
    
    def _compute_checksum(self, data: bytes) -> str:
        """Compute SHA256 checksum of data."""
        return hashlib.sha256(data).hexdigest()
    
    def save(
        self,
        model: Any,
        path: str,
        include_metadata: bool = True,
    ) -> str:
        """Save a model to disk.
        
        Args:
            model: Model to save
            path: Directory to save to
            include_metadata: Include metadata file
            
        Returns:
            Path to saved artifact
        """
        save_dir = Path(path)
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine file names
        if self.compress:
            model_file = save_dir / "model.pkl.gz"
        else:
            model_file = save_dir / "model.pkl"
        
        metadata_file = save_dir / "metadata.json"
        
        # Serialize model
        if self.format == SerializationFormat.PICKLE:
            model_data = pickle.dumps(model)
        elif self.format == SerializationFormat.JOBLIB:
            try:
                import joblib
                model_data = pickle.dumps(model)  # Fallback for now
            except ImportError:
                model_data = pickle.dumps(model)
        else:
            model_data = pickle.dumps(model)
        
        # Compute checksum before compression
        checksum = self._compute_checksum(model_data)
        original_size = len(model_data)
        
        # Compress if requested
        if self.compress:
            model_data = gzip.compress(model_data, compresslevel=self.compression_level)
            compressed_size = len(model_data)
        else:
            compressed_size = None
        
        # Write model
        with open(model_file, "wb") as f:
            f.write(model_data)
        
        # Create artifact metadata
        artifact = ModelArtifact(
            model_id=getattr(model, "model_id", ""),
            model_name=getattr(model, "name", model.__class__.__name__),
            model_type=getattr(model, "_metadata", {}).model_type if hasattr(model, "_metadata") else "",
            model_class=f"{model.__class__.__module__}.{model.__class__.__name__}",
            format=self.format,
            compressed=self.compress,
            main_file=model_file.name,
            size_bytes=original_size,
            compressed_size_bytes=compressed_size,
            checksum=checksum,
        )
        
        # Save metadata
        if include_metadata:
            with open(metadata_file, "w") as f:
                json.dump(artifact.model_dump(mode="json"), f, indent=2, default=str)
            
            # Also save model's own metadata if available
            if hasattr(model, "_metadata"):
                config_file = save_dir / "config.json"
                with open(config_file, "w") as f:
                    json.dump(model._metadata.model_dump(mode="json"), f, indent=2, default=str)
        
        return str(save_dir)
    
    def load(
        self,
        path: str,
        verify_checksum: bool = True,
    ) -> Any:
        """Load a model from disk.
        
        Args:
            path: Path to model directory or file
            verify_checksum: Verify integrity checksum
            
        Returns:
            Loaded model
        """
        load_path = Path(path)
        
        # Determine paths
        if load_path.is_dir():
            # Check for compressed first
            if (load_path / "model.pkl.gz").exists():
                model_file = load_path / "model.pkl.gz"
                compressed = True
            else:
                model_file = load_path / "model.pkl"
                compressed = False
            metadata_file = load_path / "metadata.json"
        else:
            model_file = load_path
            metadata_file = load_path.parent / "metadata.json"
            compressed = model_file.suffix == ".gz"
        
        # Load metadata
        artifact = None
        if metadata_file.exists():
            with open(metadata_file) as f:
                artifact = ModelArtifact(**json.load(f))
        
        # Read model data
        with open(model_file, "rb") as f:
            model_data = f.read()
        
        # Decompress if needed
        if compressed:
            model_data = gzip.decompress(model_data)
        
        # Verify checksum
        if verify_checksum and artifact and artifact.checksum:
            computed_checksum = self._compute_checksum(model_data)
            if computed_checksum != artifact.checksum:
                raise ValueError(
                    f"Checksum mismatch: expected {artifact.checksum}, "
                    f"got {computed_checksum}"
                )
        
        # Deserialize
        model = pickle.loads(model_data)
        
        return model
    
    def get_artifact_info(self, path: str) -> ModelArtifact:
        """Get artifact metadata without loading the model.
        
        Args:
            path: Path to model directory
            
        Returns:
            Artifact metadata
        """
        load_path = Path(path)
        
        if load_path.is_dir():
            metadata_file = load_path / "metadata.json"
        else:
            metadata_file = load_path.parent / "metadata.json"
        
        if not metadata_file.exists():
            raise FileNotFoundError(f"No metadata found at {metadata_file}")
        
        with open(metadata_file) as f:
            return ModelArtifact(**json.load(f))
    
    def export_onnx(
        self,
        model: Any,
        path: str,
        input_shape: tuple,
        input_names: Optional[list[str]] = None,
        output_names: Optional[list[str]] = None,
    ) -> str:
        """Export model to ONNX format.
        
        Args:
            model: Model to export
            path: Output path
            input_shape: Shape of input tensor
            input_names: Names for input tensors
            output_names: Names for output tensors
            
        Returns:
            Path to ONNX file
        """
        # This would require torch and onnx
        # Placeholder implementation
        raise NotImplementedError("ONNX export not yet implemented")


class ModelCache:
    """In-memory cache for loaded models."""
    
    def __init__(self, max_size: int = 10):
        """Initialize the cache.
        
        Args:
            max_size: Maximum number of models to cache
        """
        self.max_size = max_size
        self._cache: Dict[str, tuple[Any, datetime]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get a model from cache.
        
        Args:
            key: Cache key (usually model_id:version_id)
            
        Returns:
            Cached model or None
        """
        if key in self._cache:
            model, _ = self._cache[key]
            # Update access time
            self._cache[key] = (model, utc_now())
            return model
        return None
    
    def put(self, key: str, model: Any) -> None:
        """Put a model in cache.
        
        Args:
            key: Cache key
            model: Model to cache
        """
        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        
        self._cache[key] = (model, utc_now())
    
    def remove(self, key: str) -> None:
        """Remove a model from cache.
        
        Args:
            key: Cache key
        """
        if key in self._cache:
            del self._cache[key]
    
    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
    
    def __len__(self) -> int:
        return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        return key in self._cache
