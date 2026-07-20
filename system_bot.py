"""SystemBot — system administration utilities for Brain Server."""

import logging
import shutil
import subprocess

log = logging.getLogger("brain.system_bot")


class SystemBot:
    """Provides system health checks and command execution."""

    @staticmethod
    def check_disk() -> dict:
        """Check disk usage."""
        usage = shutil.disk_usage("/")
        percent = usage.used / usage.total * 100
        return {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "percent": round(percent, 1),
        }

    @staticmethod
    def check_memory() -> dict:
        """Check memory usage."""
        try:
            mem = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split()
                    if parts[0] == "MemTotal:":
                        mem["total_kb"] = int(parts[1])
                    elif parts[0] == "MemAvailable:":
                        mem["available_kb"] = int(parts[1])
            if "total_kb" in mem and "available_kb" in mem:
                used = mem["total_kb"] - mem["available_kb"]
                mem["used_kb"] = used
                mem["percent"] = round(used / mem["total_kb"] * 100, 1)
            return mem
        except Exception:
            return {"error": "cannot read memory info"}

    @staticmethod
    def check_service(name: str) -> dict:
        """Check if a service/process is running."""
        try:
            result = subprocess.run(
                ["pgrep", "-f", name],
                capture_output=True,
                timeout=5,
            )
            pids = result.stdout.decode().strip().split()
            return {"name": name, "running": len(pids) > 0, "pids": pids[:5]}
        except Exception as e:
            return {"name": name, "running": False, "error": str(e)}

    @staticmethod
    def run_command(cmd: str, timeout: int = 30) -> dict:
        """Run a shell command and return output."""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, timeout=timeout
            )
            return {
                "stdout": result.stdout.decode()[:2000],
                "stderr": result.stderr.decode()[:1000],
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"command timed out after {timeout}s"}
        except Exception as e:
            return {"error": str(e)}
