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
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = os.environ.get("CHROME") or next((p for p in [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
] if os.path.exists(p)), None)

CW, CH = 1280, 720          # 设计画布
SW, SH = 1920, 1080         # shader 渲染尺寸 = 画布 ×1.5
SCALE = SW / CW
DPI = 96                    # 1 in = 96 px -> 1 px = 0.75 pt
SLIDE_W_IN, SLIDE_H_IN = 13.333, 7.5


def px_in(v):  return v / DPI
def px_pt(v):  return v * 72.0 / DPI


# ---------------------------------------------------------------- 背景渲染

def render_bg(cfg, out_png):
    """cfg = {preset, time}；只画 shader，不带任何文字。"""
    if not CHROME:
        sys.exit("找不到 Chrome，请设置 CHROME=/path/to/chrome")
    tpl = (Path(__file__).parent / "template.html").read_text(encoding="utf-8")
    cfg = dict(cfg)
    # template 里的坐标是 1920×1080 舞台系；把画布坐标 ×1.5 传进去
    for k in ("kickerTop", "titleTop", "subTop", "bodyTop"):
        if k in cfg:
            cfg[k] = cfg[k] * SCALE
    html = tpl.replace("__CFG__", json.dumps(cfg, ensure_ascii=False))
    tmpdir = Path(tempfile.mkdtemp())
    tmp = tmpdir / "s.html"
    tmp.write_text(html, encoding="utf-8")
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--use-gl=angle",
                        "--use-angle=swiftshader", f"--screenshot={out_png}",
                        f"--window-size={SW},{SH}", "--virtual-time-budget=2500",
                        f"file://{tmp}"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return out_png


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
            _style_run(run, rs)


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
    slide.shapes.add_picture(str(src), Inches(px_in(el["x"])), Inches(px_in(el["y"])),
                             Inches(px_in(el["w"])), Inches(px_in(el["h"])))


# ---------------------------------------------------------------- 组装

def _legacy(slide):
    """老的 title/titleTop 写法 -> elements。"""
    out = []
    if slide.get("kicker"):
        out.append({"type": "text", "x": 72, "y": 44, "w": 700, "text": slide["kicker"],
                    "sizePt": 10, "color": "#8FA3B8", "font": "Menlo", "spc": 0.42})
    if slide.get("title"):
        out.append({"type": "text", "x": 72, "y": slide.get("titleTop", 300),
                    "w": 1136, "text": slide["title"], "sizePt": 66,
                    "color": "#FFFFFF", "font": "Songti SC", "bold": True})
    if slide.get("sub"):
        out.append({"type": "text", "x": 74, "y": slide.get("subTop", (slide.get("titleTop", 300)) + 110),
                    "w": 1136, "text": slide["sub"], "sizePt": 19,
                    "color": "#E8C9A8", "font": "PingFang SC"})
    if slide.get("body"):
        out.append({"type": "text", "x": 72, "y": slide.get("bodyTop", 520),
                    "w": 640, "text": slide["body"], "sizePt": 20,
                    "color": "#EDE3D6", "font": "PingFang SC"})
    return out


def build_pptx(deck, out, only=None):
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W_IN)
    prs.slide_height = Inches(SLIDE_H_IN)
    blank = prs.slide_layouts[6]
    base = deck.get("_base", ".")
    pngs = []

    for i, s in enumerate(deck["slides"]):
        if only and (i + 1) not in only:
            continue
        png = str(Path(out).with_suffix("")) + f"_bg{i}.png"
        if not s.get("background"):
            cfg = {"preset": s.get("preset") or deck.get("preset"),
                   "time": s.get("time", i * 1.7)}
            render_bg(cfg, png)
            pngs.append(png)

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
            slide.shapes.add_picture(png, 0, 0,
                                     width=prs.slide_width, height=prs.slide_height)

        for el in (s.get("elements") or _legacy(s)):
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
    return pngs


def main():
    ap = argparse.ArgumentParser(description="deck.json -> 光影背景 -> 可编辑 pptx")
    ap.add_argument("deck")
    ap.add_argument("--out", default="out/deck.pptx")
    ap.add_argument("--preset", default=None, help="cinematic / editorial / signal")
    ap.add_argument("--png-only", action="store_true")
    ap.add_argument("--pages", default="", help="只渲某几页，如 2,3")
    args = ap.parse_args()

    path = Path(args.deck).resolve()
    deck = json.loads(path.read_text(encoding="utf-8"))
    deck["_base"] = str(path.parent)

    if args.preset:
        pj = Path(__file__).parent / "presets" / f"{args.preset}.json"
        if not pj.exists():
            sys.exit(f"没有 preset: {args.preset}")
        deck["preset"] = json.loads(pj.read_text(encoding="utf-8"))

    only = {int(x) for x in args.pages.split(",") if x.strip()} or None
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    if args.png_only:
        pngs = [render_bg({"preset": s.get("preset") or deck.get("preset"),
                           "time": s.get("time", i * 1.7)},
                          str(Path(args.out).with_suffix("")) + f"_bg{i}.png")
                for i, s in enumerate(deck["slides"])
                if not only or (i + 1) in only]
        print("done:", len(pngs), "张背景")
        return

    pngs = build_pptx(deck, args.out, only)
    print(f"done: {args.out} | {len(pngs)} 页")


if __name__ == "__main__":
    main()
