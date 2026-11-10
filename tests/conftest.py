import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:       # 允许不 pip install 直接 pytest
    sys.path.insert(0, str(ROOT))
