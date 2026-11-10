"""preset 是 deck 外观的唯一来源：文件必须合法，网页上的副本必须跟着走。"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PRESET_DIR = ROOT / "deck_shader" / "presets"
NAMES = sorted(p.stem for p in PRESET_DIR.glob("*.json"))


def _load(name):
    return json.loads((PRESET_DIR / f"{name}.json").read_text(encoding="utf-8"))


def test_five_presets_ship():
    assert NAMES == ["cinematic", "dawn", "editorial", "glass", "signal"]


@pytest.mark.parametrize("name", NAMES)
def test_preset_shape(name):
    p = _load(name)
    assert re.fullmatch(r"#[0-9a-fA-F]{6}", p["light"]), "light 要是 #rrggbb"
    assert len(p["origin"]) == 2 and all(isinstance(v, (int, float)) for v in p["origin"])
    assert len(p["dir"]) == 2 and any(p["dir"]), "dir 不能是零向量"
    assert 0 < p["intensity"] <= 3
    assert 0 < p["width"] <= 4
    assert 0 <= p["haze"] <= 2
    assert 0 <= p["floor"] <= 3
    assert -1 < p["horizon"] < 1
    assert 0 <= p["grain"] <= 0.05


def _playground_presets():
    """docs/index.html 里内联了一份 PRESETS，用来看图说话，别让它悄悄跑偏。"""
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    m = re.search(r"const PRESETS=\{(\s*.*?)\n\};", html, re.S)
    assert m, "docs/index.html 里找不到 PRESETS"
    out = {}
    for name, body in re.findall(r"(\w+):(\{[^{}]*\})", m.group(1), re.S):
        quoted = re.sub(r"([{,]\s*)(\w+)\s*:", r'\1"\2":', body.replace("'", '"'))
        out[name] = json.loads(quoted)
    return out


def test_playground_matches_presets():
    page = _playground_presets()
    assert sorted(page) == NAMES
    for name in NAMES:
        disk = _load(name)
        for k, v in disk.items():
            assert page[name][k] == v, f"docs/index.html 的 {name}.{k} 和 presets/{name}.json 不一致"
