from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class PluginInterface(ABC):
    """Abstract base class for all plugins."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the plugin."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the plugin name."""
        pass

    @abstractmethod
    def get_version(self) -> str:
        """Return the plugin version."""
        pass

    @abstractmethod
    def execute(self, action: str, params: Dict[str, Any]) -> Any:
        """Execute a plugin action with given parameters."""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return plugin metadata."""
        pass


class PluginBase(BaseModel, PluginInterface):
    """Base class for plugins with common fields."""
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    dependencies: List[str] = []
    config: Dict[str, Any] = {}

    def initialize(self) -> None:
        """Default initialization."""
        pass

    def get_name(self) -> str:
        return self.name

    def get_version(self) -> str:
        return self.version

    def execute(self, action: str, params: Dict[str, Any]) -> Any:
        """Default execute - can be overridden."""
        raise NotImplementedError(f"Action '{action}' not implemented")

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "dependencies": self.dependencies,
        }