"""GPU inventory helper used by the GenLab API.

This module does not implement or alter any M5GP evolutionary operation.  It is
kept beside the canonical source only so the backend can enumerate physical
CUDA devices before it starts an isolated M5GP worker process.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import subprocess


@dataclass(frozen=True)
class CUDADevice:
    id: int
    name: str
    memory_total_mb: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _configured_count() -> int | None:
    value = os.getenv("GENLAB_GPU_COUNT", "").strip()
    if not value:
        return None
    try:
        return max(0, int(value))
    except ValueError:
        return None


def _from_nvidia_smi() -> list[CUDADevice]:
    command = [
        "nvidia-smi",
        "--query-gpu=index,name,memory.total",
        "--format=csv,noheader,nounits",
    ]
    try:
        output = subprocess.check_output(
            command,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return []

    devices: list[CUDADevice] = []
    for line in output.splitlines():
        values = [value.strip() for value in line.split(",")]
        if len(values) < 2:
            continue
        try:
            device_id = int(values[0])
            memory = int(values[2]) if len(values) > 2 else None
        except ValueError:
            continue
        devices.append(CUDADevice(device_id, values[1], memory))
    return devices


def list_cuda_devices() -> list[CUDADevice]:
    """Return physical CUDA devices without importing CuPy, Numba, or M5GP."""
    count = _configured_count()
    if count is not None:
        return [CUDADevice(index, f"CUDA GPU {index}") for index in range(count)]
    return _from_nvidia_smi()


__all__ = ["CUDADevice", "list_cuda_devices"]
