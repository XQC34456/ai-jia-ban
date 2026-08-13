"""确保 `from app import ...` 在测试中可用。"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
