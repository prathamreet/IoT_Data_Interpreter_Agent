"""Ensure the repo root is importable so `import backend...` works in tests."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
