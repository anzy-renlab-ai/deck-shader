"""真渲：需要 Chrome。没有 Chrome 的机器上自动跳过，不让 CI 变成薛定谔的绿。"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from deck_shader import cli

ROOT = Path(__file__).resolve().parent.parent
needs_chrome = pytest.mark.skipif(not cli.CHROME, reason="没有安装 Chrome")


def run(args, cwd=None):
    return subprocess.run([sys.executable, "-m", "deck_shader.cli", *args],
                          cwd=cwd or ROOT, capture_output=True, text=True)


@needs_chrome
def test_precision_deck_builds(tmp_path):
    out = tmp_path / "deck.pptx"
    r = run(["examples/precision/deck.json", "--out", str(out)])
    assert r.returncode == 0, r.stderr
    assert out.exists()

    from pptx import Presentation
    prs = Presentation(str(out))
    assert len(prs.slides) == 4

    # 两张 shader 背景 + 两张纯色
    pics = [sh for sh in prs.slides[0].shapes if sh.shape_type == 13]
    assert pics, "封面应该有一张背景图"

    # 文字必须是原生文本框，不是图片
    texts = [sh.text_frame.text for sh in prs.slides[0].shapes if sh.has_text_frame]
    joined = "".join(texts)
    assert "幻灯片的光" in joined

    # 演讲备注要写进去
    assert prs.slides[0].notes_slide.notes_text_frame.text.strip()


@needs_chrome
def test_background_is_small(tmp_path):
    r = run(["examples/precision/deck.json", "--out", str(tmp_path / "d.pptx"), "--png-only"])
    assert r.returncode == 0, r.stderr
    jpgs = list(tmp_path.glob("*_bg*.jpg"))
    assert len(jpgs) == 2
    for f in jpgs:
        assert f.stat().st_size < 400_000, f"{f.name} 有 {f.stat().st_size/1e6:.1f} MB，太大了"


@needs_chrome
def test_png_flag(tmp_path):
    r = run(["examples/precision/deck.json", "--out", str(tmp_path / "d.pptx"),
             "--png-only", "--png", "--pages", "1"])
    assert r.returncode == 0, r.stderr
    pngs = list(tmp_path.glob("*_bg*.png"))
    assert len(pngs) == 1


@needs_chrome
def test_render_is_deterministic(tmp_path):
    """同一个 deck 渲两次必须一模一样——这是它比文生图可控的地方。"""
    from PIL import Image, ImageStat

    deck = {"preset": {"light": "#ffc98a", "origin": [0.5, 0.85], "dir": [-0.4, -1]},
            "slides": [{"time": 1.5}]}
    src = tmp_path / "one.json"
    src.write_text(json.dumps(deck), encoding="utf-8")

    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        r = run([str(src), "--out", str(d / "d.pptx"), "--png-only"])
        assert r.returncode == 0, r.stderr
    pa, pb = a / "d_bg0.jpg", b / "d_bg0.jpg"
    assert pa.exists() and pb.exists()
    assert pa.read_bytes() == pb.read_bytes()

    with Image.open(pa) as im:
        assert ImageStat.Stat(im.convert("L")).stddev[0] > 3, "背景不该是一张纯色图"
