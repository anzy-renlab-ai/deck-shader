"""不碰 Chrome 的那部分：输入校验、老格式转换、参数错误。"""
import json
from pathlib import Path

import pytest

from deck_shader import cli

ROOT = Path(__file__).resolve().parent.parent


def _write(tmp_path, obj, name="deck.json"):
    p = tmp_path / name
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")
    return p


def test_missing_file(tmp_path):
    with pytest.raises(SystemExit) as e:
        cli._load_deck(tmp_path / "nope.json")
    assert "找不到" in str(e.value)


def test_broken_json(tmp_path):
    p = _write(tmp_path, '{"slides": [')
    with pytest.raises(SystemExit) as e:
        cli._load_deck(p)
    assert "不是合法 JSON" in str(e.value)


def test_no_slides(tmp_path):
    for bad in ({}, {"slides": {}}, []):
        p = _write(tmp_path, bad)
        with pytest.raises(SystemExit) as e:
            cli._load_deck(p)
        assert "slides" in str(e.value)


def test_empty_slides(tmp_path):
    p = _write(tmp_path, {"slides": []})
    with pytest.raises(SystemExit) as e:
        cli._load_deck(p)
    assert "空的" in str(e.value)


def test_unknown_preset_lists_the_real_ones(tmp_path):
    p = _write(tmp_path, {"slides": [{}]})
    with pytest.raises(SystemExit) as e:
        cli._load_deck(p, "nope")
    assert "cinematic" in str(e.value)


def test_preset_override_wins(tmp_path):
    p = _write(tmp_path, {"slides": [{}], "preset": {"light": "#123456"}})
    deck = cli._load_deck(p, "dawn")
    assert deck["preset"]["light"] == "#ffb08a"


def test_preset_as_name_resolves(tmp_path):
    p = _write(tmp_path, {"preset": "dawn", "slides": [{}]})
    deck = cli._load_deck(p)
    assert deck["preset"]["light"] == "#ffb08a"


def test_slide_preset_as_name_resolves(tmp_path):
    p = _write(tmp_path, {"slides": [{"preset": "glass"}, {}]})
    deck = cli._load_deck(p)
    assert deck["slides"][0]["preset"]["width"] == 0.5
    assert "preset" not in deck["slides"][1]


def test_unknown_preset_name_in_deck(tmp_path):
    p = _write(tmp_path, {"preset": "neon", "slides": [{}]})
    with pytest.raises(SystemExit) as e:
        cli._load_deck(p)
    assert "neon" in str(e.value) and "cinematic" in str(e.value)


def test_unknown_preset_name_on_slide_says_which_page(tmp_path):
    p = _write(tmp_path, {"slides": [{}, {"preset": "neon"}]})
    with pytest.raises(SystemExit) as e:
        cli._load_deck(p)
    assert "第 2 页" in str(e.value)


def test_preset_wrong_type(tmp_path):
    p = _write(tmp_path, {"preset": 5, "slides": [{}]})
    with pytest.raises(SystemExit) as e:
        cli._load_deck(p)
    assert "preset" in str(e.value)


def test_legacy_uses_style():
    els = cli._legacy({"title": "T", "sub": "S", "body": "B"},
                      {"font": "Noto Serif SC", "titleColor": "123456",
                       "subColor": "#ABCDEF", "bodyColor": "000000"})
    by = {e["text"]: e for e in els}
    assert by["T"]["font"] == "Noto Serif SC" and by["T"]["color"] == "123456"
    assert by["S"]["color"] == "#ABCDEF"
    assert by["B"]["color"] == "000000"


def test_legacy_without_style_still_works():
    els = cli._legacy({"title": "T"})
    assert els[0]["color"] == "#FFFFFF" and els[0]["bold"] is True


def test_element_without_type(tmp_path):
    p = _write(tmp_path, {"slides": [{"elements": [{"x": 0, "y": 0}]}]})
    with pytest.raises(SystemExit) as e:
        cli._load_deck(p)
    assert "第 1 页第 1 个元素" in str(e.value)


def test_element_missing_coordinates(tmp_path):
    p = _write(tmp_path, {"slides": [{"elements": [{"type": "text", "y": 0, "text": "a"}]}]})
    with pytest.raises(SystemExit) as e:
        cli._load_deck(p)
    assert "缺少数值 x" in str(e.value)


def test_image_requires_src(tmp_path):
    p = _write(tmp_path, {"slides": [{"elements": [{"type": "image", "x": 0, "y": 0, "w": 10}]}]})
    with pytest.raises(SystemExit) as e:
        cli._load_deck(p)
    assert "缺少 src" in str(e.value)


def test_legacy_slides_skip_element_validation(tmp_path):
    p = _write(tmp_path, {"slides": [{"title": "只有标题"}]})
    assert cli._load_deck(p)["slides"]


def _slide():
    from pptx import Presentation
    prs = Presentation()
    return prs.slides.add_slide(prs.slide_layouts[6])


def test_run_without_styling_inherits_from_element():
    el = {"type": "text", "x": 0, "y": 0, "w": 400, "sizePt": 28, "color": "#FF0000",
          "paragraphs": [{"runs": [{"text": "只有文字"}]}]}
    cli._add_text(_slide(), el)
    el = {"type": "text", "x": 0, "y": 0, "w": 400,
          "paragraphs": [{"runs": [{"text": "只有文字"}]}]}
    cli._add_text(_slide(), el)          # 不该 KeyError


def test_cache_key_changes_with_quality_and_config(tmp_path):
    cfg = {"preset": {"light": "#ffffff"}, "time": 0}
    out = tmp_path / "bg.jpg"
    _, a = cli._cache_file(cfg, str(out), 92)
    _, b = cli._cache_file(cfg, str(out), 80)
    _, c = cli._cache_file({**cfg, "time": 1.7}, str(out), 92)
    _, d = cli._cache_file(cfg, str(out), 92)
    assert a == d and a != b and a != c


def test_cache_hit_does_not_launch_chrome(tmp_path, monkeypatch):
    out = tmp_path / "bg.jpg"
    cfg = {"preset": {"light": "#ffffff"}, "time": 0}
    cache_dir, cache_file = cli._cache_file(cfg, str(out), 92)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(b"from-cache")
    monkeypatch.setattr(cli, "CHROME", "/definitely/not/chrome")

    cli.render_bg(cfg, str(out), 92, cache=True)
    assert out.read_bytes() == b"from-cache"


def test_no_cache_flag_skips_the_cache(tmp_path, monkeypatch):
    out = tmp_path / "bg.jpg"
    cfg = {"preset": {"light": "#ffffff"}, "time": 0}
    cache_dir, cache_file = cli._cache_file(cfg, str(out), 92)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(b"from-cache")
    monkeypatch.setattr(cli, "CHROME", "/definitely/not/chrome")

    with pytest.raises(FileNotFoundError):
        cli.render_bg(cfg, str(out), 92, cache=False)


def test_text_entirely_off_canvas_warns(tmp_path, capsys):
    p = _write(tmp_path, {"slides": [{"elements": [
        {"type": "text", "x": 72, "y": 900, "w": 600, "text": "看不见"}]}]})
    cli._load_deck(p)                                  # 不报错，只警告
    assert "画布外面" in capsys.readouterr().err


def test_image_bleeding_off_canvas_is_fine(tmp_path, capsys):
    p = _write(tmp_path, {"slides": [{"elements": [
        {"type": "image", "src": "a.png", "x": -40, "y": -40, "w": 200, "h": 200}]}]})
    cli._load_deck(p)
    assert capsys.readouterr().err == ""


def test_examples_are_loadable():
    for d in sorted((ROOT / "examples").iterdir()):
        deck = cli._load_deck(d / "deck.json")
        assert deck["slides"]


def test_cli_pages_requires_png_only(monkeypatch):
    monkeypatch.setattr("sys.argv", ["deck-shader", "x.json", "--pages", "1"])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert "--png-only" in str(e.value)


def test_cli_version(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["deck-shader", "--version"])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 0
    from deck_shader import __version__
    assert __version__ in capsys.readouterr().out


def test_quality_range(monkeypatch):
    monkeypatch.setattr("sys.argv", ["deck-shader", "x.json", "--quality", "0"])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert "1–100" in str(e.value)


def test_pages_out_of_range(monkeypatch, tmp_path):
    p = _write(tmp_path, {"slides": [{}, {}]})
    monkeypatch.setattr("sys.argv", ["deck-shader", str(p), "--pages", "5", "--png-only"])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert "只有 2 页" in str(e.value)
