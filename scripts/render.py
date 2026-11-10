#!/usr/bin/env python3
"""deck-shader MVP: deck.json -> WebGL 背景 -> 原生 pptx（文字可编辑）。

用法:
  python3 render.py deck.json --out out/deck.pptx
  python3 render.py deck.json --png-only          # 只出图
"""
import json, os, subprocess, sys, tempfile, shutil
from pathlib import Path

CHROME = os.environ.get("CHROME") or next((p for p in [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
] if os.path.exists(p)), None)
if not CHROME:
    sys.exit("找不到 Chrome，请设置 CHROME=/path/to/chrome")
W, H = 1920, 1080
PX = W / 13.333  # 144 px per inch

def render_bg(cfg, out_png):
    tpl = Path(__file__).with_name("template.html").read_text(encoding="utf-8")
    html = tpl.replace("__CFG__", json.dumps(cfg, ensure_ascii=False))
    tmp = Path(tempfile.mkdtemp()) / "s.html"
    tmp.write_text(html, encoding="utf-8")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--use-gl=angle",
                    "--use-angle=swiftshader", f"--screenshot={out_png}",
                    f"--window-size={W},{H}", "--virtual-time-budget=2500",
                    f"file://{tmp}"], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(tmp.parent, ignore_errors=True)

def add_text(slide, cfg, style):
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    def box(left_px, top_px, width_px, text, size_px, color, spacing=0, bold=True):
        if not text: return
        left, top = left_px/PX, top_px/PX
        w = width_px/PX
        tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(w), Inches(0.2))
        tf = tb.text_frame; tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        lines = text.split("\n")
        for i, line in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            run = p.add_run(); run.text = line
            f = run.font
            f.size = Pt(size_px/2); f.bold = bold
            f.name = style.get("font", "Songti SC")
            f.color.rgb = RGBColor.from_string(color)
            if spacing:
                from pptx.oxml.ns import qn
                f.element.rPr.set("spc", str(int(spacing*100)))

    box(110, cfg.get("titleTop", 300), 1500, cfg.get("title"), 84, style.get("titleColor", "FFFFFF"))
    box(114, cfg.get("subTop", cfg.get("titleTop", 300)+140), 1500, cfg.get("sub"), 26, style.get("subColor", "E8C9A8"))
    box(110, cfg.get("bodyTop", 520), 820, cfg.get("body"), 27, style.get("bodyColor", "EDE3D6"), bold=False)

def build_pptx(deck, out):
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    style = deck.get("style", {})
    pngs = []
    for i, s in enumerate(deck["slides"]):
        cfg = {"preset": s.get("preset", deck.get("preset")), "time": s.get("time", i*1.7)}
        png = str(Path(out).with_suffix("")) + f"_bg{i}.png"
        render_bg(cfg, png); pngs.append(png)
        slide = prs.slides.add_slide(blank)
        slide.shapes.add_picture(png, 0, 0, width=prs.slide_width, height=prs.slide_height)
        add_text(slide, s, style)
        if s.get("notes"):
            slide.notes_slide.notes_text_frame.text = s["notes"]
    prs.save(out)
    return pngs

if __name__ == "__main__":
    deck_path = sys.argv[1]
    deck = json.loads(Path(deck_path).read_text(encoding="utf-8"))
    if "--preset" in sys.argv:
        name = sys.argv[sys.argv.index("--preset")+1]
        deck["preset"] = json.loads((Path(__file__).parent.parent/"presets"/f"{name}.json").read_text(encoding="utf-8"))
    out = "out/deck.pptx"
    if "--out" in sys.argv: out = sys.argv[sys.argv.index("--out")+1]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    pngs = build_pptx(deck, out)
    print("done:", out, "| backgrounds:", len(pngs))
