"""Incident classification using NLP."""

from datetime import datetime
from typing import Any, Optional, List, Dict
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id
from autosre.ml.common.base import (
    BaseMLModel,
    TrainingConfig,
    EvaluationMetrics,
    PredictionResult,
    ModelStatus,
    ModelVersion,
)
from autosre.ml.common.preprocessing import TextPreprocessor


class IncidentCategory(str, Enum):
    """Category of incident."""
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    NETWORK = "network"
    DATABASE = "database"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DEPLOYMENT = "deployment"
    CONFIGURATION = "configuration"
    EXTERNAL = "external"
    OTHER = "other"


class ClassificationResult(BaseModel):
    """Result of incident classification."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    # Primary classification
    category: IncidentCategory = Field(default=IncidentCategory.OTHER)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # All probabilities
    category_probabilities: dict[str, float] = Field(default_factory=dict)
    
    # Secondary classifications
    subcategory: str = Field(default="")
    tags: list[str] = Field(default_factory=list)
    
    # Extracted info
    affected_services: list[str] = Field(default_factory=list)
    error_types: list[str] = Field(default_factory=list)
    
    # Model info
    model_id: str = Field(default="")
    
    # Timing
    classification_time_ms: float = Field(default=0.0, ge=0.0)


class IncidentClassifier(BaseMLModel[str, ClassificationResult]):
    """Classify incidents based on text description.
    
    Uses text features to classify incidents into categories:
    - Infrastructure issues
    - Application errors
    - Network problems
    - Database issues
    - Security incidents
    - Performance degradation
    - Deployment failures
    - Configuration errors
    
    Features:
    - Keyword matching
    - TF-IDF features
    - Entity extraction
    """
    
    def __init__(
        self,
        use_tfidf: bool = True,
        max_features: int = 1000,
        ngram_range: tuple = (1, 2),
    ):
        """Initialize the classifier.
        
        Args:
            use_tfidf: Use TF-IDF features
            max_features: Maximum features for TF-IDF
            ngram_range: N-gram range
        """
        super().__init__(
            name="incident_classifier",
            model_type="incident_classifier",
            hyperparameters={
                "use_tfidf": use_tfidf,
                "max_features": max_features,
                "ngram_range": ngram_range,
            },
        )
        
        self.use_tfidf = use_tfidf
        self.max_features = max_features
        self.ngram_range = ngram_range
        
        self._preprocessor = TextPreprocessor(
            lowercase=True,
            remove_punctuation=False,
        )
        
        # Category keywords
        self._category_keywords: Dict[IncidentCategory, List[str]] = {
            IncidentCategory.INFRASTRUCTURE: [
                "server", "vm", "instance", "node", "cluster", "kubernetes", "k8s",
                "docker", "container", "pod", "host", "machine", "hardware",
                "disk", "memory", "cpu", "storage", "infra",
            ],
            IncidentCategory.APPLICATION: [
                "application", "app", "service", "microservice", "api", "endpoint",
                "crash", "exception", "error", "bug", "code", "null", "undefined",
                "stacktrace", "traceback",
            ],
            IncidentCategory.NETWORK: [
                "network", "dns", "connection", "timeout", "latency", "firewall",
                "port", "tcp", "udp", "http", "https", "ssl", "tls", "certificate",
                "load balancer", "proxy", "routing",
            ],
            IncidentCategory.DATABASE: [
                "database", "db", "sql", "query", "postgres", "mysql", "mongo",
                "redis", "cache", "replication", "deadlock", "lock", "transaction",
                "index", "table", "schema",
            ],
            IncidentCategory.SECURITY: [
                "security", "auth", "authentication", "authorization", "permission",
                "access", "denied", "unauthorized", "breach", "attack", "ddos",
                "vulnerability", "exploit", "injection", "xss", "csrf",
            ],
            IncidentCategory.PERFORMANCE: [
                "slow", "latency", "performance", "response time", "throughput",
                "bottleneck", "degradation", "spike", "high load", "memory leak",
                "cpu spike", "queue", "backlog",
            ],
            IncidentCategory.DEPLOYMENT: [
                "deploy", "deployment", "release", "rollout", "rollback",
                "ci/cd", "pipeline", "build", "version", "upgrade", "migration",
            ],
            IncidentCategory.CONFIGURATION: [
                "config", "configuration", "settings", "environment", "variable",
                "misconfiguration", "parameter", "value", "yaml", "json",
            ],
            IncidentCategory.EXTERNAL: [
                "external", "third-party", "vendor", "provider", "aws", "gcp",
                "azure", "cloud", "api", "integration", "upstream", "downstream",
            ],
        }
        
        # TF-IDF vocabulary
        self._vocabulary: Dict[str, int] = {}
        self._idf: np.ndarray = np.array([])
        
        # Class weights
        self._class_weights: Dict[IncidentCategory, np.ndarray] = {}
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text.
        
        Args:
            text: Input text
            
        Returns:
            List of tokens
        """
        processed = self._preprocessor.preprocess(text)
        tokens = processed.split()
        
        # Add bigrams
        if self.ngram_range[1] >= 2:
            for i in range(len(tokens) - 1):
                tokens.append(f"{tokens[i]}_{tokens[i+1]}")
        
        return tokens
    
    def _extract_features(self, text: str) -> np.ndarray:
        """Extract features from text.
        
        Args:
            text: Input text
            
        Returns:
            Feature vector
        """
        tokens = self._tokenize(text)
        
        # Create TF vector
        tf = np.zeros(len(self._vocabulary))
        for token in tokens:
            if token in self._vocabulary:
                tf[self._vocabulary[token]] += 1
        
        # Normalize
        if np.sum(tf) > 0:
            tf = tf / np.sum(tf)
        
        # Apply IDF
        if len(self._idf) == len(tf):
            tfidf = tf * self._idf
        else:
            tfidf = tf
        
        return tfidf
    
    def fit(
        self,
        X: List[str],
        y: List[IncidentCategory],
        config: Optional[TrainingConfig] = None,
    ) -> "IncidentClassifier":
        """Train the classifier.
        
        Args:
            X: Training texts
            y: Training labels
            config: Training configuration
            
        Returns:
            Self
        """
        # Build vocabulary
        all_tokens = []
        for text in X:
            all_tokens.extend(self._tokenize(text))
        
        # Count token frequencies
        from collections import Counter
        token_counts = Counter(all_tokens)
        
        # Select top features
        top_tokens = [t for t, _ in token_counts.most_common(self.max_features)]
        self._vocabulary = {token: i for i, token in enumerate(top_tokens)}
        
        # Calculate IDF
        n_docs = len(X)
        doc_freq = np.zeros(len(self._vocabulary))
        
        for text in X:
            tokens = set(self._tokenize(text))
            for token in tokens:
                if token in self._vocabulary:
                    doc_freq[self._vocabulary[token]] += 1
        
        self._idf = np.log((n_docs + 1) / (doc_freq + 1)) + 1
        
        # Extract features for all documents
        X_features = np.array([self._extract_features(text) for text in X])
        
        # Calculate class centroids
        for category in IncidentCategory:
            indices = [i for i, label in enumerate(y) if label == category]
            if indices:
                centroid = np.mean(X_features[indices], axis=0)
                self._class_weights[category] = centroid
        
        self._is_fitted = True
        self._metadata.status = ModelStatus.TRAINED
        self._metadata.last_trained_at = utc_now()
        
        version = ModelVersion(
            description=f"Trained on {len(X)} incidents",
            metrics={
                "num_samples": float(len(X)),
                "vocab_size": float(len(self._vocabulary)),
            },
        )
        self._metadata.add_version(version)
        
        return self
    
    def predict(
        self,
        X: str,
    ) -> PredictionResult[ClassificationResult]:
        """Classify an incident.
        
        Args:
            X: Incident text
            
        Returns:
            Classification result
        """
        import time
        start_time = time.time()
        
        text_lower = X.lower()
        
        # Keyword-based scoring
        scores: Dict[IncidentCategory, float] = {}
        
        for category, keywords in self._category_keywords.items():
            score = 0.0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 1.0
            scores[category] = score
        
        # TF-IDF scoring if fitted
        if self._is_fitted and self._class_weights:
            features = self._extract_features(X)
            
            for category, centroid in self._class_weights.items():
                similarity = np.dot(features, centroid) / (
                    np.linalg.norm(features) * np.linalg.norm(centroid) + 1e-10
                )
                scores[category] = scores.get(category, 0) + similarity * 10
        
        # Normalize scores to probabilities
        total = sum(scores.values()) + 1e-10
        probabilities = {cat.value: score / total for cat, score in scores.items()}
        
        # Get best category
        best_category = max(scores.keys(), key=lambda k: scores[k])
        confidence = probabilities[best_category.value]
        
        # Extract services
        affected_services = self._extract_services(text_lower)
        
        # Extract error types
        error_types = self._extract_error_types(text_lower)
        
        # Generate tags
        tags = self._generate_tags(text_lower)
        
        result = ClassificationResult(
            category=best_category,
            confidence=confidence,
            category_probabilities=probabilities,
            affected_services=affected_services,
            error_types=error_types,
            tags=tags,
            model_id=self.model_id,
            classification_time_ms=(time.time() - start_time) * 1000,
        )
        
        return PredictionResult(
            prediction=result,
            confidence=confidence,
            model_id=self.model_id,
            latency_ms=(time.time() - start_time) * 1000,
        )
    
    def _extract_services(self, text: str) -> List[str]:
        """Extract mentioned service names.
        
        Args:
            text: Input text
            
        Returns:
            List of service names
        """
        import re
        
        services = []
        
        # Pattern: service-name, service_name
        patterns = [
            r'service[:\s]+([a-z0-9\-_]+)',
            r'([a-z]+)-(?:service|api|app)',
            r'([a-z]+)_(?:service|api|app)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            services.extend(matches)
        
        return list(set(services))[:10]
    
    def _extract_error_types(self, text: str) -> List[str]:
        """Extract error types from text.
        
        Args:
            text: Input text
            
        Returns:
            List of error types
        """
        error_types = []
        
        patterns = [
            (r'(\w+error)\b', True),
            (r'(\w+exception)\b', True),
            (r'(timeout)', False),
            (r'(connection refused)', False),
            (r'(out of memory)', False),
            (r'(permission denied)', False),
            (r'(not found)', False),
            (r'(internal server error)', False),
        ]
        
        for pattern, is_regex in patterns:
            import re
            if is_regex:
                matches = re.findall(pattern, text, re.IGNORECASE)
                error_types.extend(matches)
            else:
                if pattern in text.lower():
                    error_types.append(pattern)
        
        return list(set(error_types))[:10]
    
    def _generate_tags(self, text: str) -> List[str]:
        """Generate tags for the incident.
        
        Args:
            text: Input text
            
        Returns:
            List of tags
        """
        tags = []
        
        tag_keywords = {
            "critical": ["critical", "severe", "emergency", "outage"],
            "degraded": ["slow", "degraded", "degradation"],
            "intermittent": ["intermittent", "flapping", "sometimes"],
            "customer-facing": ["customer", "user", "frontend", "production"],
            "internal": ["internal", "backend", "staging"],
        }
        
        for tag, keywords in tag_keywords.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        
        return tags
    
    def evaluate(
        self,
        X: List[str],
        y: List[IncidentCategory],
    ) -> EvaluationMetrics:
        """Evaluate the classifier."""
        import time
        start_time = time.time()
        
        predictions = []
        for text in X:
            result = self.predict(text)
            predictions.append(result.prediction.category)
        
        # Calculate accuracy
        correct = sum(1 for p, true in zip(predictions, y) if p == true)
        accuracy = correct / len(y) if y else 0
        
        return EvaluationMetrics(
            accuracy=float(accuracy),
            dataset_size=len(y),
            evaluation_time_seconds=(time.time() - start_time),
        )
    
    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance."""
        if not self._vocabulary:
            return {}
        
        # Return top keywords
        importance = {}
        for category, keywords in self._category_keywords.items():
            for kw in keywords[:5]:
                importance[f"{category.value}:{kw}"] = 1.0 / (len(keywords) + 1)
        
        return importance
