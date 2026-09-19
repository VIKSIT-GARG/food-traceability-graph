#!/usr/bin/env python3
"""Build generator script.

Moved to scripts/build_v2.py.
Delegating execution to scripts/build_v2.py.
"""
from pathlib import Path
import runpy

scripts_build = Path(__file__).resolve().parent / "scripts" / "build_v2.py"
if __name__ == "__main__":
    runpy.run_path(str(scripts_build), run_name="__main__")