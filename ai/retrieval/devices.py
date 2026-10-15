"""Lazy, explicit device selection for local inference models."""

from typing import Literal


Device = Literal["cpu", "mps", "cuda"]


def resolve_device(requested: str) -> Device:
    """Auto selects an available GPU; explicit GPU requests never fall back.

    Import torch only when preparing a run or loading inference resources.
    Settings and health checks must remain independent of accelerator startup.
    """
    if requested == "cpu":
        return "cpu"
    if requested not in {"auto", "mps", "cuda"}:
        raise ValueError("device must be auto, cpu, mps or cuda")
    import torch

    if requested == "auto":
        if torch.cuda.is_available():
            return "cuda"
        return "mps" if torch.backends.mps.is_available() else "cpu"
    available = torch.backends.mps.is_available() if requested == "mps" else torch.cuda.is_available()
    if not available:
        raise RuntimeError(f"Requested {requested} device is unavailable in this process")
    return requested
