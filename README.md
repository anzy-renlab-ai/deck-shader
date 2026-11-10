<div align="center">

<img src="docs/loop.gif" width="880" alt="deck-shader: a volumetric light beam rendered by a fragment shader, under editable slide text">

# deck-shader

**Decks whose light is computed, not painted.**

Write a JSON file. A shader renders the light — volumetric beams, caustics, drifting dust — and you get a `.pptx` where the text is still editable.

`python3 scripts/render.py examples/hello/deck.json`

<a href="https://anzy-renlab-ai.github.io/deck-shader/"><b>▶ Try it live in the browser — no install</b></a>

<sub>A 6-second render from `examples/hello`. The text is native PowerPoint text; only the light is baked.</sub>

</div>

---

## The problem

Every slide background you have ever made is one of three things: a flat gradient, a stock photo, or a blurred blob someone spent twenty minutes on.

None of them have light. They have *the suggestion of* light — a Photoshop drop shadow, a radial gradient, an overlay at 12% opacity.

Light is a physical process. It scatters through dust, bends at a surface, casts caustics on a floor. That is a few lines of math, and your GPU has been able to do it in real time since 2010.

So: describe the slide in JSON, render the light with a fragment shader, and lay native PowerPoint text on top.

```
deck.json  ──►  WebGL shader  ──►  background.png  ──►  .pptx (editable text)
```

## What you get

| | |
|---|---|
| `.pptx` | 13.33 × 7.5 in, background is a rendered image, **all text is native and editable** |
| `.png` | 1920 × 1080 background plates, if you want to compose in Figma or Keynote |
| `notes` | per-slide speaker notes, written straight into the pptx |

## Quickstart

```bash
git clone https://github.com/anzy-renlab-ai/deck-shader
cd deck-shader
pip install python-pptx
python3 scripts/render.py examples/hello/deck.json --out out/hello.pptx
```

Requires Chrome (headless, for the WebGL pass). macOS path is auto-detected; override with `CHROME=/path/to/chrome`.

## A slide is a list of elements at exact coordinates

<img src="docs/precision-02.png" width="880" alt="A paper-white slide: kicker, title, two columns split by a 1px rule at x=656, one red sentence">

Content slides are not "title + bullets + a theme". Every element is placed by
hand — a text box at `x: 704`, a 1px rule at `x: 656`, a 96px number that is
allowed to be bigger than the title because on this page it is the subject.

```json
{ "type": "rect", "x": 656, "y": 208, "w": 1, "h": 116, "fill": "#D8DEE4" },
{ "type": "text", "x": 704, "y": 238, "w": 504, "h": 120, "paragraphs": [
    { "align": "left", "lineSpacingPct": 170, "runs": [
      { "text": "每一页只描述它自己要说的那件事。", "sizePt": 17,
        "color": "#142B40", "font": "PingFang SC" } ] } ] }
```

Three element types: `text` (paragraphs → runs, each with its own font, size,
color, letter-spacing), `rect` (hairlines, fills, dividers), `image`.

Canvas is **1280 × 720**. 1 px = 0.75 pt, 1 in = 96 px — the numbers are the
same ones you'd read off a Figma inspect panel, so you can measure once and
type it in.

<img src="docs/precision-03.png" width="880" alt="Three large numbers — 72, 1, 1 — each with a label and a two-line explanation">

The full example is `examples/precision/`.

### Why coordinates and not a layout engine

A layout engine chooses where things go. That is exactly the thing you cannot
delegate when the deck has to say something: the sentence that matters gets the
same weight as the sentence that doesn't, and all ten slides come out looking
like the same slide.

Templates are *selected*. Coordinates are *written*. The difference shows up as
whether a page can be louder than the page before it.

## A deck is a JSON file

```json
{
  "preset": { "light": "#ffc98a", "origin": [0.55, 0.85], "dir": [-0.42, -1.0], "intensity": 1.0 },
  "style":  { "font": "Songti SC", "titleColor": "FFFFFF" },
  "slides": [
    {
      "kicker": "DECK · SHADER",
      "title": "光线是可以计算的",
      "titleTop": 330,
      "sub": "把 PPT 的背景交给 WebGL",
      "subTop": 470,
      "notes": "开场：先让他们注意到光，再注意到字。"
    }
  ]
}
```

| field | meaning |
|---|---|
| `preset.light` | light color |
| `preset.origin` | where the beam enters, in normalized stage coords |
| `preset.dir` | beam direction |
| `preset.intensity` | how hard it hits |
| `time` | shader time; change it and the dust moves, the beam breathes |

## Why this exists

Two observations.

**One.** A deck is read in three seconds, and the first thing anyone perceives is not your words — it is the light in the room. Slides with real light read as *staged*; slides with gradients read as *slides*.

**Two.** Agent skills that "generate decks" all stop at layout. They arrange boxes. None of them render anything. The moment you want a背景 that looks photographed, you are back in Photoshop.

This is the missing layer: a renderer, not a template.

## Roadmap

- [x] volumetric beam + floor caustics + dust, parameterized
- [x] JSON → PNG → editable `.pptx`
- [x] absolute element model: `text` / `rect` / `image` at 1280×720, 1px = 0.75pt
- [ ] presets: `editorial`, `glass`, `dawn`, `signal`
- [ ] video export (15s loop, for social covers)
- [x] HTML runtime (same shader, live in a browser)
- [ ] paper mode: arXiv PDF → deck outline → rendered deck

## Works as an agent skill

`SKILL.md` is included. Drop the folder into `~/.claude/skills/` (Claude Code), `~/.workbuddy/skills/` (WorkBuddy), or any host that reads `SKILL.md`, and the agent can render decks directly.

## License

MIT.
