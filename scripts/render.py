#!/usr/bin/env python3
"""兼容入口：真正的实现在 deck_shader/cli.py（pip 包里是同一个文件）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from deck_shader.cli import main

if __name__ == "__main__":
    main()
