#!/usr/bin/env python3
"""deck-shader: deck.json -> WebGL 背景 -> 原生 pptx（每个元素都可编辑）。

画布 1280×720，绝对坐标，1 px = 0.75 pt，1 in = 96 px。
元素模型照抄「代码精准控制」那一套：text / rect / image，全部写死坐标。

用法:
  python3 render.py deck.json --out out/deck.pptx
  python3 render.py deck.json --png-only
  python3 render.py deck.json --pages 2,3        # 只渲某几页
  python3 render.py deck.json --preset cinematic
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    from . import __version__
except ImportError:                        # 直接 python deck_shader/cli.py 跑
    __version__ = "0.2.0"

def _find_chrome():
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    fixed = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    local = os.environ.get("LOCALAPPDATA")
    if local:                                    # Windows：装在用户目录下也要认
        fixed.append(os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"))
    for p in fixed:
        if os.path.exists(p):
            return p
    for name in ("google-chrome", "chrome", "chromium", "chromium-browser"):
        p = shutil.which(name)
        if p:
            return p
    return None


CHROME = _find_chrome()

CW, CH = 1280, 720          # 设计画布
SW, SH = 1920, 1080         # shader 渲染尺寸 = 画布 ×1.5
SCALE = SW / CW
DPI = 96                    # 1 in = 96 px -> 1 px = 0.75 pt
SLIDE_W_IN, SLIDE_H_IN = 13.333, 7.5


def px_in(v):  return v / DPI
def px_pt(v):  return v * 72.0 / DPI


# ---------------------------------------------------------------- 背景渲染

def _screenshot(html_path, out, size=(SW, SH)):
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--use-gl=angle",
                        "--use-angle=swiftshader", f"--screenshot={out}",
                        f"--window-size={size[0]},{size[1]}", "--virtual-time-budget=2500",
                        Path(html_path).resolve().as_uri()], check=True, timeout=90,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except subprocess.TimeoutExpired:
        _die("Chrome 90 秒没渲完，可能是 CHROME 指向的不是 Chrome/Chromium")
    except subprocess.CalledProcessError as e:
        tail = (e.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-6:]
        _die("Chrome 渲染失败：\n  " + "\n  ".join(tail))
    if not Path(out).exists():
        _die(f"Chrome 没有写出 {out}")


def _looks_blank(path):
    """WebGL 挂了的话多半是一张纯色图——这种情况要报错，不能悄悄交出去。"""
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return False
    with Image.open(path) as im:
        return sum(ImageStat.Stat(im.convert("L")).stddev) < 0.5


def _to_jpeg(src_png, out_jpg, quality):
    """PNG 很贵：1920×1080 的暗部渐变一张 1.7 MB，转 JPEG 只要 ~160 KB。

    没有 Pillow 就退回到让 Chrome 直接写 .jpg（画质固定，但不用装东西）。
    """
    try:
        from PIL import Image
    except ImportError:
        return None
    im = Image.open(src_png).convert("RGB")
    # subsampling=0：暗部大面积渐变，色度抽样会在光束边缘留绿边
    im.save(out_jpg, "JPEG", quality=quality, subsampling=0, optimize=True)
    return out_jpg


def _reject_blank(path):
    if _looks_blank(path):
        _die("背景是一张纯色图——WebGL 没跑起来，试试换一台机器或加 --use-angle=metal")


CACHE_DIRNAME = ".deck-shader-cache"


def _cache_file(cfg, out_img, quality):
    """同一份配置 + 同一个 template 出来的必然是同一种光，存一次就够。

    改一个数字重渲染时，没动过的页直接命中，十页 deck 只等一页。
    """
    tpl = (Path(__file__).parent / "template.html").read_bytes()
    h = hashlib.sha1(json.dumps(cfg, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    h.update(tpl)
    h.update(f"|q{quality}|{SW}x{SH}|{Path(out_img).suffix.lower()}".encode())
    d = Path(out_img).parent / CACHE_DIRNAME
    return d, d / f"{h.hexdigest()[:20]}{Path(out_img).suffix.lower()}"


def _store_cache(src, cache_dir, cache_file):
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cache_file.with_suffix(cache_file.suffix + ".tmp")
        shutil.copyfile(src, tmp)
        os.replace(tmp, cache_file)          # 并行渲染时不能留半个文件
    except OSError:
        pass                                  # 缓存坏了不该拖垮渲染


def render_bg(cfg, out_img, quality=92, cache=True):
    """cfg = {preset, time}；只画 shader，不带任何文字。"""
    if not CHROME:
        sys.exit("找不到 Chrome，请设置 CHROME=/path/to/chrome")
    tpl = (Path(__file__).parent / "template.html").read_text(encoding="utf-8")
    cfg = dict(cfg)
    # template 里的坐标是 1920×1080 舞台系；把画布坐标 ×1.5 传进去
    for k in ("kickerTop", "titleTop", "subTop", "bodyTop"):
        if k in cfg:
            cfg[k] = cfg[k] * SCALE
    cache_dir, cache_file = _cache_file(cfg, out_img, quality)
    if cache and cache_file.exists() and cache_file.stat().st_size > 0:
        shutil.copyfile(cache_file, out_img)
        return out_img
    html = tpl.replace("__CFG__", json.dumps(cfg, ensure_ascii=False))
    tmpdir = Path(tempfile.mkdtemp())
    tmp_html = tmpdir / "s.html"
    tmp_html.write_text(html, encoding="utf-8")
    want_jpeg = out_img.lower().endswith((".jpg", ".jpeg"))
    try:
        if not want_jpeg:
            _screenshot(tmp_html, out_img)
            _reject_blank(out_img)
        else:
            tmp_png = tmpdir / "shot.png"
            _screenshot(tmp_html, tmp_png)
            _reject_blank(tmp_png)
            if _to_jpeg(tmp_png, out_img, quality) is None:
                _screenshot(tmp_html, out_img)     # 没有 Pillow：交给 Chrome 写 JPEG
        if cache:
            _store_cache(out_img, cache_dir, cache_file)
        return out_img
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------- 元素绘制

def _set_font(run, name):
    """python-pptx 的 font.name 只写 latin；中文要补 a:ea。"""
    from pptx.oxml.ns import qn
    run.font.name = name
    rPr = run.font._rPr
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", name)


def _style_run(run, spec):
    from pptx.util import Pt
    from pptx.dml.color import RGBColor
    f = run.font
    f.size = Pt(px_pt(spec["sizePt"]))
    f.bold = spec.get("bold", False)
    f.italic = spec.get("italic", False)
    if spec.get("color"):
        f.color.rgb = RGBColor.from_string(spec["color"].lstrip("#").upper())
    _set_font(run, spec.get("font", "PingFang SC"))
    if spec.get("spc"):
        run.font._rPr.set("spc", str(int(spec["spc"] * 100)))


def _add_text(slide, el):
    from pptx.util import Inches, Pt
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

    tb = slide.shapes.add_textbox(Inches(px_in(el["x"])), Inches(px_in(el["y"])),
                                  Inches(px_in(el["w"])), Inches(px_in(el.get("h", 20))))
    tf = tb.text_frame
    tf.word_wrap = el.get("wrap", True)
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE,
                          "bottom": MSO_ANCHOR.BOTTOM}.get(el.get("valign", "top"), MSO_ANCHOR.TOP)

    paras = el.get("paragraphs")
    if paras is None:  # 简写：单段单 run
        paras = [{"align": el.get("align", "left"),
                  "runs": [{"text": el.get("text", ""),
                            "sizePt": el.get("sizePt", 20),
                            "color": el.get("color", "#142B40"),
                            "font": el.get("font", "PingFang SC"),
                            "bold": el.get("bold", False)}]}]

    amap = {"left": PP_ALIGN.LEFT, "right": PP_ALIGN.RIGHT,
            "center": PP_ALIGN.CENTER, "justify": PP_ALIGN.JUSTIFY}
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = amap.get(p.get("align", "left"), PP_ALIGN.LEFT)
        if p.get("lineSpacingPct"):
            para.line_spacing = p["lineSpacingPct"] / 100.0
        if p.get("spaceBeforePt"):
            para.space_before = Pt(p["spaceBeforePt"])
        for rs in p.get("runs", []):
            run = para.add_run()
            run.text = rs.get("text", "")
            # 一个 run 只写 text 是常态；字号/颜色/字体从元素上继承，
            # 不该因为少写一个 sizePt 就 KeyError 崩在这里。
            spec = {"sizePt": el.get("sizePt", 20),
                    "color": el.get("color", "#142B40"),
                    "font": el.get("font", "PingFang SC"),
                    **rs}
            _style_run(run, spec)


def _add_rect(slide, el):
    from pptx.util import Inches, Pt
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.dml.color import RGBColor
    from pptx.oxml.ns import qn

    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(px_in(el["x"])),
                                Inches(px_in(el["y"])), Inches(px_in(el["w"])),
                                Inches(px_in(el.get("h", 1))))
    sh.shadow.inherit = False
    # 去掉主题自带的 <p:style>：它会在 LibreOffice / Keynote 里带出投影和圆角
    style = sh._element.find(qn("p:style"))
    if style is not None:
        sh._element.remove(style)
    if el.get("fill"):
        sh.fill.solid()
        sh.fill.fore_color.rgb = RGBColor.from_string(el["fill"].lstrip("#").upper())
    else:
        sh.fill.background()
    st = el.get("stroke")
    if st:
        sh.line.color.rgb = RGBColor.from_string(st.get("color", "#D8DEE4").lstrip("#").upper())
        sh.line.width = Pt(st.get("widthPt", 1))
    else:
        sh.line.fill.background()
    return sh


def _add_image(slide, el, base):
    from pptx.util import Inches
    src = Path(el["src"])
    if not src.is_absolute():
        src = Path(base) / src
    if not src.exists():
        _die(f"图片不存在：{src}（image 元素的 src 是相对 deck.json 的路径）")
    slide.shapes.add_picture(str(src), Inches(px_in(el["x"])), Inches(px_in(el["y"])),
                             Inches(px_in(el["w"])), Inches(px_in(el["h"])))


# ---------------------------------------------------------------- 组装

def _legacy(slide, style=None):
    """老的 title/titleTop 写法 -> elements。style 里的字体和颜色在这里生效。"""
    st = style or {}
    font = st.get("font", "Songti SC")
    out = []
    if slide.get("kicker"):
        out.append({"type": "text", "x": 72, "y": 44, "w": 700, "text": slide["kicker"],
                    "sizePt": 10, "color": st.get("kickerColor", "#8FA3B8"),
                    "font": "Menlo", "spc": 0.42})
    if slide.get("title"):
        out.append({"type": "text", "x": 72, "y": slide.get("titleTop", 300),
                    "w": 1136, "text": slide["title"], "sizePt": 66,
                    "color": st.get("titleColor", "#FFFFFF"), "font": font, "bold": True})
    if slide.get("sub"):
        out.append({"type": "text", "x": 74, "y": slide.get("subTop", (slide.get("titleTop", 300)) + 110),
                    "w": 1136, "text": slide["sub"], "sizePt": 19,
                    "color": st.get("subColor", "#E8C9A8"),
                    "font": st.get("subFont", "PingFang SC")})
    if slide.get("body"):
        out.append({"type": "text", "x": 72, "y": slide.get("bodyTop", 520),
                    "w": 640, "text": slide["body"], "sizePt": 20,
                    "color": st.get("bodyColor", "#EDE3D6"),
                    "font": st.get("subFont", "PingFang SC")})
    return out


def _jobs():
    return max(1, min(4, os.cpu_count() or 1))


def _die(msg):
    sys.exit(f"deck-shader: {msg}")


def render_backgrounds(deck, out, only=None, ext=".jpg", quality=92, cache=True):
    """把所有需要的背景渲完（可并行），返回 {slide_index: path}。"""
    stem = str(Path(out).with_suffix(""))
    todo = [(i, s) for i, s in enumerate(deck["slides"])
            if (not only or (i + 1) in only) and not s.get("background")]
    if not todo:
        return {}
    paths = {}
    with ThreadPoolExecutor(max_workers=_jobs()) as pool:
        futs = {}
        for i, s in todo:
            cfg = {"preset": s.get("preset") or deck.get("preset"),
                   "time": s.get("time", i * 1.7)}
            p = f"{stem}_bg{i}{ext}"
            paths[i] = p
            futs[pool.submit(render_bg, cfg, p, quality, cache)] = i
        for f, i in futs.items():
            f.result()          # 出错就在这里炸，别等到组装 pptx
    return paths


def build_pptx(deck, out, only=None, ext=".jpg", quality=92, cache=True):
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W_IN)
    prs.slide_height = Inches(SLIDE_H_IN)
    blank = prs.slide_layouts[6]
    base = deck.get("_base", ".")
    bgs = render_backgrounds(deck, out, only, ext, quality, cache)

    for i, s in enumerate(deck["slides"]):
        if only and (i + 1) not in only:
            continue
        slide = prs.slides.add_slide(blank)
        bg = s.get("background")
        if bg and bg.startswith("#"):
            from pptx.dml.color import RGBColor
            fill = slide.background.fill
            fill.solid()
            fill.fore_color.rgb = RGBColor.from_string(bg.lstrip("#").upper())
        elif bg:
            p = Path(bg)
            if not p.is_absolute():
                p = Path(base) / p
            slide.shapes.add_picture(str(p), 0, 0,
                                     width=prs.slide_width, height=prs.slide_height)
        else:
            slide.shapes.add_picture(bgs[i], 0, 0,
                                     width=prs.slide_width, height=prs.slide_height)

        els = s.get("elements") or _legacy(s, deck.get("style"))
        for el in els:
            kind = el.get("type")
            if kind == "text":
                _add_text(slide, el)
            elif kind == "rect":
                _add_rect(slide, el)
            elif kind == "image":
                _add_image(slide, el, base)
            else:
                print(f"  ! 第 {i+1} 页未知元素类型 {kind}", file=sys.stderr)

        if s.get("notes"):
            slide.notes_slide.notes_text_frame.text = s["notes"]

    prs.save(out)
    return list(bgs.values())


def _validate(deck, name):
    """写错的坐标不该等到 pptx 打开才发现——这里一次性说清楚是哪一页哪个元素。"""
    kinds = {"text", "rect", "image"}
    for where, val in (("顶层", deck.get("preset")),):
        if val is not None and not isinstance(val, (str, dict)):
            _die(f"{name} {where}的 preset 要写成预设名（字符串）或参数对象，收到 {type(val).__name__}")
    for si, s in enumerate(deck["slides"], 1):
        if not isinstance(s, dict):
            _die(f"{name} 第 {si} 页不是一个对象（应该是 {{...}}）")
        pv = s.get("preset")
        if pv is not None and not isinstance(pv, (str, dict)):
            _die(f"{name} 第 {si} 页的 preset 要写成预设名（字符串）或参数对象，"
                 f"收到 {type(pv).__name__}")
        els = s.get("elements")
        if els is None:
            continue                      # 老格式，title/sub/body 那种
        if not isinstance(els, list):
            _die(f"{name} 第 {si} 页的 elements 要是数组")
        for ei, el in enumerate(els, 1):
            where = f"{name} 第 {si} 页第 {ei} 个元素"
            if not isinstance(el, dict):
                _die(f"{where} 不是对象")
            kind = el.get("type")
            if kind not in kinds:
                _die(f"{where} 的 type 是 {kind!r}，只能是 {'/'.join(sorted(kinds))}")
            for k in ("x", "y"):
                if not isinstance(el.get(k), (int, float)):
                    _die(f"{where}（{kind}）缺少数值 {k}")
            if kind in ("rect", "image") and not isinstance(el.get("w"), (int, float)):
                _die(f"{where}（{kind}）缺少宽度 w")
            if kind == "image" and not el.get("src"):
                _die(f"{where}（image）缺少 src")
            if kind == "text" and not el.get("paragraphs") and "text" not in el:
                _die(f"{where}（text）既没有 text 也没有 paragraphs")
            _warn_offstage(el, kind, where)


def _warn_offstage(el, kind, where):
    """整块跑到画布外面的文字，永远不会出现在观众眼里。

    只有 text 才报：图片和矩形超出边界是正常出血，不算错。
    """
    if kind != "text":
        return
    x, y = el["x"], el["y"]
    w = el.get("w") or 0
    h = el.get("h") or 20
    if x + w <= 0 or y + h <= 0 or x >= CW or y >= CH:
        print(f"  ! {where}（text）整块在 {CW}×{CH} 画布外面，观众看不到它",
              file=sys.stderr)


def _preset_by_name(name, where=""):
    pj = Path(__file__).parent / "presets" / f"{name}.json"
    if not pj.exists():
        have = ", ".join(sorted(p.stem for p in (Path(__file__).parent / "presets").glob("*.json")))
        _die(f"{where+' 的' if where else ''}没有 preset：{name}（有：{have}）")
    return json.loads(pj.read_text(encoding="utf-8"))


def _load_deck(path, preset_override=None):
    if not path.exists():
        _die(f"找不到 {path}")
    try:
        deck = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _die(f"{path.name} 不是合法 JSON：第 {e.lineno} 行第 {e.colno} 列 — {e.msg}")
    if not isinstance(deck, dict) or not isinstance(deck.get("slides"), list):
        _die(f'{path.name} 里没有 slides 数组（顶层应该是 {{"slides": [ ... ]}}）')
    if not deck["slides"]:
        _die(f"{path.name} 的 slides 是空的")
    deck["_base"] = str(path.parent)
    _validate(deck, path.name)

    if preset_override:
        deck["preset"] = _preset_by_name(preset_override)

    # "preset": "glass" 这种写法也要认——否则字符串会被当成参数对象，
    # shader 读不到任何一个字段，安安静静画出一张没调过的默认光。
    if isinstance(deck.get("preset"), str):
        deck["preset"] = _preset_by_name(deck["preset"])
    for si, s in enumerate(deck["slides"], 1):
        if isinstance(s, dict) and isinstance(s.get("preset"), str):
            s["preset"] = _preset_by_name(s["preset"], where=f"第 {si} 页")
    return deck


def main():
    ap = argparse.ArgumentParser(
        prog="deck-shader",
        description="deck.json -> shader 光影背景 -> 文字仍可编辑的 pptx")
    ap.add_argument("deck", help="deck.json 路径")
    ap.add_argument("--out", default="out/deck.pptx", help="输出路径（默认 out/deck.pptx）")
    ap.add_argument("--preset", default=None,
                    help="cinematic / editorial / signal / glass / dawn")
    ap.add_argument("--png-only", action="store_true", help="只出背景图，不组 pptx")
    ap.add_argument("--pages", default="", help="只渲染某几页，如 2,3（需配合 --png-only）")
    ap.add_argument("--png", action="store_true", help="背景存 PNG（无损，但一张 ~1.7 MB）")
    ap.add_argument("--quality", type=int, default=92, metavar="1-100",
                    help="JPEG 质量，默认 92")
    ap.add_argument("--no-cache", action="store_true",
                    help="忽略背景缓存，全部重渲（改过 shader 但没改 template 时用）")
    ap.add_argument("--version", action="version", version=f"deck-shader {__version__}")
    args = ap.parse_args()

    if args.pages and not args.png_only:
        _die("--pages 只用于 --png-only；生成 pptx 时不能只留几页")
    if not 1 <= args.quality <= 100:
        _die(f"--quality 要在 1–100，收到 {args.quality}")

    ext = ".png" if args.png else ".jpg"
    path = Path(args.deck).resolve()
    deck = _load_deck(path, args.preset)

    only = None
    if args.pages:
        try:
            only = {int(x) for x in args.pages.split(",") if x.strip()}
        except ValueError:
            _die(f"--pages 要写成 2,3 这样，收到 {args.pages!r}")
        n = len(deck["slides"])
        if not only or max(only) > n or min(only) < 1:
            _die(f"--pages {args.pages} 超出范围：这份 deck 只有 {n} 页")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    if args.png_only:
        bgs = render_backgrounds(deck, args.out, only, ext, args.quality,
                                 not args.no_cache)
        if not bgs:
            print("这个范围里没有需要渲染的页（都是纯色/图片背景）")
            return
        print("done:", len(bgs), "张背景 ->", ", ".join(bgs.values()))
        return

    bgs = build_pptx(deck, args.out, only, ext, args.quality, not args.no_cache)
    mb = os.path.getsize(args.out) / 1e6
    print(f"done: {args.out} | {len(deck['slides'])} 页 | {len(bgs)} 张背景 | {mb:.1f} MB")


if __name__ == "__main__":
    main()
