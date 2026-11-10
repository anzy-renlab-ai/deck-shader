---
name: deck-shader
description: "Render presentation decks whose backgrounds are computed by a WebGL shader (volumetric light, caustics, dust) instead of gradients or stock images, then export a .pptx whose text is still editable. Use when the user wants a deck, keynote, pitch, or slide deck with cinematic light, or says the backgrounds look flat, generic, or 'like a template'. Triggers: deck, slides, presentation, 幻灯片, PPT, 光影, 质感."
metadata:
  author: anzy-renlab-ai
  version: "0.1"
---

# deck-shader

A deck is a JSON file. A fragment shader renders the light. The text stays native.

```
deck.json ──► WebGL (headless Chrome) ──► background.png ──► .pptx
```

## When to use

- The user wants a deck with real light: beams, caustics, dust, depth.
- The user complains that a deck looks flat, templated, or "like every other pitch deck".
- You need 16:9 background plates at 1920×1080 for Keynote, Figma, or video.
- **Not** for: data-heavy internal reports (use a normal template), decks that must open on a machine without the background images, or anything under 3 slides.

## Build a deck

1. Write `deck.json`. One object per slide. Canvas is **1280 × 720**, absolute
   coordinates, 1 px = 0.75 pt.

```json
{
  "preset": {"light": "#ffc98a", "origin": [0.55, 0.85], "dir": [-0.42, -1.0], "intensity": 1.0},
  "slides": [
    {
      "time": 2.0,
      "background": "#FCFBF9",
      "notes": "演讲备注",
      "elements": [
        {"type": "text", "x": 72, "y": 44, "w": 600, "text": "§ 01 · 两种做法",
         "sizePt": 10, "color": "#6B7078", "font": "Menlo", "spc": 0.42},
        {"type": "rect", "x": 72, "y": 176, "w": 1136, "h": 1, "fill": "#D8DEE4"},
        {"type": "text", "x": 72, "y": 96, "w": 900, "text": "标题即结论",
         "sizePt": 40, "color": "#142B40", "font": "PingFang SC", "bold": true},
        {"type": "image", "src": "assets/band.jpg", "x": 1100, "y": 0, "w": 108, "h": 658}
      ]
    }
  ]
}
```

| field | notes |
|---|---|
| `background` | omit → shader render. `"#FCFBF9"` → solid fill. `"bg.png"` → image |
| `time` | shader time; change it and the dust moves |
| `type: text` | `paragraphs[]` → `runs[]`; each run has `text/sizePt/color/font/bold/spc` |
| `type: rect` | `fill` or `stroke:{color,widthPt}`; this is how hairlines are made |
| `type: image` | `src` relative to the deck file |
| legacy | `title`/`titleTop`/`sub`/`body` still work, auto-converted |

2. Render:

```bash
python3 scripts/render.py deck.json --out out/deck.pptx
```

3. Open the pptx. Background is a rendered image; **every text box is native** — edit it in PowerPoint like any other deck.

`examples/precision/` is the reference: paper-white content pages, 72px margins,
a 1px rule at `x = 656`, one accent per page.

## Rules that make it look good

- **One light per deck.** Change `origin`/`dir` between sections, not between slides.
- **Text never sits in the beam.** Put type on the dark side; the beam is the subject on the title slide, the frame on content slides.
- **≤ 5 lines per slide.** The renderer gives you depth, not room.
- **Don't put shader light under a text-heavy page.** A beam behind body copy is unreadable. Use a solid background on content slides and save the shader for the 1–2 stage pages.
- **Margins are 72, structure lines are 1px.** Pick the numbers once and reuse them; that is what makes ten pages look like one deck.
- **One accent per page.** The page says one thing, so exactly one thing is colored.
- **Notes are mandatory.** A rendered deck without speaker notes is a poster.
- **Check the output.** Always rasterize one slide (`soffice --headless --convert-to pdf`) and look at it before delivering.

## Presets

| name | light | mood |
|---|---|---|
| `cinematic` | `#ffc98a` | warm key light, dark stage |
| `editorial` | `#e8e2d6` | cold paper light, high contrast |
| `signal` | `#7fd1ff` | blue monitor glow |

Pass `--preset <name>` or set `preset` in the JSON.

## Limitations

- Backgrounds are baked images: ~1.5 MB per slide at 1920×1080.
- Headless Chrome is required (SwiftShader fallback works without a GPU).
- CJK fonts fall back to the system serif if the named font is missing.
