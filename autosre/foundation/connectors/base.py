"""
Base Connector - Abstract interface for all data source connectors.

All connectors inherit from this and implement the sync() method
to pull data from their respective sources.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ConnectorConfig(BaseModel):
    """Base configuration for connectors."""
    enabled: bool = Field(default=True)
    sync_interval_seconds: int = Field(default=300, description="How often to sync")
    last_sync: Optional[datetime] = None


class ConnectorStatus(BaseModel):
    """Status of a connector."""
    name: str
    enabled: bool
    connected: bool
    last_sync: Optional[datetime]
    error: Optional[str] = None
    items_synced: int = 0


class BaseConnector(ABC):
    """
    Abstract base class for data source connectors.
    
    Each connector is responsible for:
    1. Connecting to an external data source
    2. Pulling data and normalizing it to AutoSRE models
    3. Storing the data in the context store
    """
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize the connector.
        
        Args:
            config: Configuration dictionary for the connector
        """
        self.config = config or {}
        self._connected = False
        self._last_sync: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._items_synced = 0
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the connector name."""
        pass
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the data source.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the data source."""
        pass
    
    @abstractmethod
    async def sync(self, context_store: Any) -> int:
        """
        Sync data from the source to the context store.
        
        Args:
            context_store: The ContextStore instance to populate
            
        Returns:
            Number of items synced
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the data source is healthy/reachable.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    def get_status(self) -> ConnectorStatus:
        """Get the current status of this connector."""
        return ConnectorStatus(
            name=self.name,
            enabled=self.config.get("enabled", True),
            connected=self._connected,
            last_sync=self._last_sync,
            error=self._last_error,
            items_synced=self._items_synced,
        )
    
    async def safe_sync(self, context_store: Any) -> int:
        """
        Sync with error handling.
        
        Returns:
            Number of items synced, 0 on error
        """
        try:
            count = await self.sync(context_store)
            self._last_sync = datetime.utcnow()
            self._last_error = None
            self._items_synced = count
            return count
        except Exception as e:
            self._last_error = str(e)
            return 0
