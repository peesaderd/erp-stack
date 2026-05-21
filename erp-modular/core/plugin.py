"""Plugin Interface - Abstract Base Class สำหรับ Plugin ใน ERP Modular"""

from abc import ABC, abstractmethod
from typing import Any


class PluginInterface(ABC):
    """Abstract Base Class ที่ Plugin ทุกตัวต้อง implement"""

    @abstractmethod
    def load(self, config: dict[str, Any]) -> None:
        """เรียกเมื่อ Plugin ถูกโหลดเข้า sistema"""
        ...

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """execute งานหลักของ Plugin"""
        ...

    @abstractmethod
    def unload(self) -> None:
        """เรียกเมื่อ Plugin ถูกเอาออกจาก sistema"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """ชื่อ Plugin"""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """เวอร์ชัน Plugin"""
        ...
