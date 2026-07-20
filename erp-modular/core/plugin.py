"""Plugin Interface - Abstract Base Class สำหรับ Plugin ใน ERP Modular

Lifecycle ของ Plugin:
1. load(config) → เรียกเมื่อ Plugin ถูกโหลด
2. install() → เรียกครั้งแรกที่ติดตั้ง (setup DB, config)
3. activate() → เรียกเมื่อเปิดใช้งาน
4. execute(**kwargs) → ทำงานหลัก
5. deactivate() → เรียกเมื่อปิดใช้งาน
6. unload() → เรียกเมื่อเอาออกจากระบบ
7. uninstall() → เรียกเมื่อถอนการติดตั้ง (cleanup)
"""

from abc import ABC, abstractmethod
from typing import Any


class PluginInterface(ABC):
    """Abstract Base Class ที่ Plugin ทุกตัวต้อง implement"""

    # ─── Properties ────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """ชื่อ Plugin (ไม่ซ้ำ)"""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """เวอร์ชัน Plugin (semver)"""
        ...

    @property
    def dependencies(self) -> list[str]:
        """รายชื่อ Plugin slugs ที่ต้องโหลดก่อน"""
        return []

    # ─── Lifecycle Hooks ──────────────────────────────────────────────────

    @abstractmethod
    def load(self, config: dict[str, Any]) -> None:
        """เรียกเมื่อ Plugin ถูกโหลดเข้า sistema
        ใช้สำหรับ: import dependencies, ตรวจสอบ environment"""
        ...

    def install(self) -> None:
        """เรียกครั้งแรกที่ติดตั้ง Plugin
        ใช้สำหรับ: สร้างตาราง DB, สร้าง config เริ่มต้น
        (ไม่ต้อง implement ถ้าไม่จำเป็น)"""
        pass

    def activate(self) -> None:
        """เรียกเมื่อ Plugin ถูกเปิดใช้งาน (enabled=true)
        ใช้สำหรับ: register routes, start background tasks
        (ไม่ต้อง implement ถ้าไม่จำเป็น)"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """execute งานหลักของ Plugin
        ใช้สำหรับ: ทำงานตามหน้าที่ของ Plugin"""
        ...

    def deactivate(self) -> None:
        """เรียกเมื่อ Plugin ถูกปิดใช้งาน (enabled=false)
        ใช้สำหรับ: unregister routes, stop background tasks
        (ไม่ต้อง implement ถ้าไม่จำเป็น)"""
        pass

    @abstractmethod
    def unload(self) -> None:
        """เรียกเมื่อ Plugin ถูกเอาออกจาก sistema
        ใช้สำหรับ: cleanup, close connections"""
        ...

    def uninstall(self) -> None:
        """เรียกเมื่อถอนการติดตั้ง Plugin
        ใช้สำหรับ: ลบตาราง DB, ลบ config
        (ไม่ต้อง implement ถ้าไม่จำเป็น)"""
        pass

    # ─── Metadata ──────────────────────────────────────────────────────────

    def get_info(self) -> dict[str, Any]:
        """ข้อมูลของ Plugin"""
        return {
            "name": self.name,
            "version": self.version,
            "dependencies": self.dependencies,
        }
