"""jevgw: one decision model at a time behind one TypeSafe-compatible /v1/systemone endpoint."""

__version__ = "0.3.0"

from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"  # the model list, the llama.cpp installer and the vendored model servers
