"""Similar incident finder using NLP."""

from datetime import datetime
from typing import Any, Optional, List, Dict
import hashlib

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id
from autosre.ml.common.preprocessing import TextPreprocessor


class SimilarIncident(BaseModel):
    """A similar past incident."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    incident_id: str = Field(default="")
    title: str = Field(default="")
    description: str = Field(default="")
    
    # Similarity
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # What matched
    matching_keywords: list[str] = Field(default_factory=list)
    matching_services: list[str] = Field(default_factory=list)
    
    # Resolution info
    resolution: str = Field(default="")
    root_cause: str = Field(default="")
    time_to_resolve_minutes: Optional[int] = None
    
    # Metadata
    occurred_at: Optional[datetime] = None
    severity: str = Field(default="")


class SimilarityResult(BaseModel):
    """Result of similarity search."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    similar_incidents: list[SimilarIncident] = Field(default_factory=list)
    
    # Statistics
    total_searched: int = Field(default=0, ge=0)
    matches_found: int = Field(default=0, ge=0)
    
    # Best match info
    best_match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    suggested_resolution: str = Field(default="")
    
    # Search info
    search_time_ms: float = Field(default=0.0, ge=0.0)


class SimilarityFinder:
    """Find similar past incidents.
    
    Uses text similarity techniques:
    - TF-IDF cosine similarity
    - Keyword matching
    - Service overlap
    - Category matching
    
    Features:
    - Fast vector similarity search
    - Semantic understanding
    - Resolution recommendations
    """
    
    def __init__(
        self,
        max_results: int = 5,
        min_similarity: float = 0.3,
        use_tfidf: bool = True,
    ):
        """Initialize the finder.
        
        Args:
            max_results: Maximum results to return
            min_similarity: Minimum similarity threshold
            use_tfidf: Use TF-IDF for similarity
        """
        self.max_results = max_results
        self.min_similarity = min_similarity
        self.use_tfidf = use_tfidf
        
        self._preprocessor = TextPreprocessor()
        
        # Incident store
        self._incidents: List[Dict[str, Any]] = []
        
        # TF-IDF parameters
        self._vocabulary: Dict[str, int] = {}
        self._idf: np.ndarray = np.array([])
        self._incident_vectors: np.ndarray = np.array([])
    
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
        bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
        
        return tokens + bigrams
    
    def _text_to_vector(self, text: str) -> np.ndarray:
        """Convert text to TF-IDF vector.
        
        Args:
            text: Input text
            
        Returns:
            TF-IDF vector
        """
        tokens = self._tokenize(text)
        
        # Term frequency
        tf = np.zeros(len(self._vocabulary))
        for token in tokens:
            if token in self._vocabulary:
                tf[self._vocabulary[token]] += 1
        
        # Normalize
        if np.sum(tf) > 0:
            tf = tf / np.sum(tf)
        
        # Apply IDF
        if len(self._idf) == len(tf):
            return tf * self._idf
        return tf
    
    def _build_index(self) -> None:
        """Build search index from incidents."""
        if not self._incidents:
            return
        
        # Build vocabulary
        all_tokens = []
        for incident in self._incidents:
            text = f"{incident.get('title', '')} {incident.get('description', '')}"
            all_tokens.extend(self._tokenize(text))
        
        from collections import Counter
        token_counts = Counter(all_tokens)
        
        # Top 5000 tokens
        top_tokens = [t for t, _ in token_counts.most_common(5000)]
        self._vocabulary = {token: i for i, token in enumerate(top_tokens)}
        
        # Calculate IDF
        n_docs = len(self._incidents)
        doc_freq = np.zeros(len(self._vocabulary))
        
        for incident in self._incidents:
            text = f"{incident.get('title', '')} {incident.get('description', '')}"
            tokens = set(self._tokenize(text))
            for token in tokens:
                if token in self._vocabulary:
                    doc_freq[self._vocabulary[token]] += 1
        
        self._idf = np.log((n_docs + 1) / (doc_freq + 1)) + 1
        
        # Build incident vectors
        vectors = []
        for incident in self._incidents:
            text = f"{incident.get('title', '')} {incident.get('description', '')}"
            vectors.append(self._text_to_vector(text))
        
        self._incident_vectors = np.array(vectors)
    
    def add_incident(
        self,
        incident_id: str,
        title: str,
        description: str,
        resolution: str = "",
        root_cause: str = "",
        severity: str = "",
        occurred_at: Optional[datetime] = None,
        time_to_resolve_minutes: Optional[int] = None,
        services: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an incident to the search index.
        
        Args:
            incident_id: Unique incident ID
            title: Incident title
            description: Incident description
            resolution: How it was resolved
            root_cause: Root cause
            severity: Severity level
            occurred_at: When it occurred
            time_to_resolve_minutes: Resolution time
            services: Affected services
            metadata: Additional metadata
        """
        incident = {
            "incident_id": incident_id,
            "title": title,
            "description": description,
            "resolution": resolution,
            "root_cause": root_cause,
            "severity": severity,
            "occurred_at": occurred_at,
            "time_to_resolve_minutes": time_to_resolve_minutes,
            "services": services or [],
            "metadata": metadata or {},
        }
        
        self._incidents.append(incident)
        
        # Rebuild index periodically
        if len(self._incidents) % 100 == 0:
            self._build_index()
    
    def add_incidents_batch(
        self,
        incidents: List[Dict[str, Any]],
    ) -> None:
        """Add multiple incidents.
        
        Args:
            incidents: List of incident dictionaries
        """
        for incident in incidents:
            self._incidents.append(incident)
        
        self._build_index()
    
    def find_similar(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> SimilarityResult:
        """Find similar incidents.
        
        Args:
            query: Query text (incident description)
            context: Additional context (services, category, etc.)
            
        Returns:
            Similarity search result
        """
        import time
        start_time = time.time()
        
        context = context or {}
        
        # Rebuild index if needed
        if len(self._incident_vectors) != len(self._incidents):
            self._build_index()
        
        if not self._incidents:
            return SimilarityResult(
                similar_incidents=[],
                total_searched=0,
                matches_found=0,
                search_time_ms=(time.time() - start_time) * 1000,
            )
        
        # Calculate query vector
        query_vector = self._text_to_vector(query)
        
        # Calculate similarities
        similarities = []
        
        for i, incident in enumerate(self._incidents):
            # TF-IDF similarity
            if self.use_tfidf and len(self._incident_vectors) > i:
                incident_vector = self._incident_vectors[i]
                cosine_sim = np.dot(query_vector, incident_vector) / (
                    np.linalg.norm(query_vector) * np.linalg.norm(incident_vector) + 1e-10
                )
            else:
                cosine_sim = 0.0
            
            # Keyword overlap
            query_tokens = set(self._tokenize(query))
            incident_text = f"{incident.get('title', '')} {incident.get('description', '')}"
            incident_tokens = set(self._tokenize(incident_text))
            
            overlap = len(query_tokens & incident_tokens)
            keyword_sim = overlap / (len(query_tokens) + 1)
            
            # Service overlap
            query_services = set(context.get("services", []))
            incident_services = set(incident.get("services", []))
            service_sim = 0.0
            if query_services and incident_services:
                service_overlap = len(query_services & incident_services)
                service_sim = service_overlap / len(query_services)
            
            # Combined similarity
            combined_sim = 0.5 * cosine_sim + 0.3 * keyword_sim + 0.2 * service_sim
            
            similarities.append((i, combined_sim, list(query_tokens & incident_tokens), list(query_services & incident_services)))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Filter and convert to results
        similar_incidents = []
        for idx, sim_score, matching_kw, matching_svc in similarities[:self.max_results]:
            if sim_score < self.min_similarity:
                break
            
            incident = self._incidents[idx]
            similar_incidents.append(SimilarIncident(
                incident_id=incident.get("incident_id", ""),
                title=incident.get("title", ""),
                description=incident.get("description", "")[:500],
                similarity_score=float(sim_score),
                matching_keywords=matching_kw[:10],
                matching_services=matching_svc,
                resolution=incident.get("resolution", ""),
                root_cause=incident.get("root_cause", ""),
                time_to_resolve_minutes=incident.get("time_to_resolve_minutes"),
                occurred_at=incident.get("occurred_at"),
                severity=incident.get("severity", ""),
            ))
        
        # Suggested resolution from best match
        suggested_resolution = ""
        if similar_incidents and similar_incidents[0].resolution:
            suggested_resolution = similar_incidents[0].resolution
        
        return SimilarityResult(
            similar_incidents=similar_incidents,
            total_searched=len(self._incidents),
            matches_found=len(similar_incidents),
            best_match_score=similar_incidents[0].similarity_score if similar_incidents else 0.0,
            suggested_resolution=suggested_resolution,
            search_time_ms=(time.time() - start_time) * 1000,
        )
    
    def clear(self) -> None:
        """Clear all incidents."""
        self._incidents.clear()
        self._vocabulary.clear()
        self._idf = np.array([])
        self._incident_vectors = np.array([])
