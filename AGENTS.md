# deck-shader for agents

Any coding agent can build a deck with this repo. There is no SDK to learn: the
input is a JSON file, the renderer is a command, and the output is a `.pptx`
whose text is still native.

This file follows the [AGENTS.md](https://agents.md) convention, so Codex,
Cursor, Amp, Jules, and anything else that reads `AGENTS.md` picks it up
automatically. Claude Code and WorkBuddy additionally read `SKILL.md`.

## Setup

```bash
pip install deck-shader        # or: uvx --from deck-shader deck-shader ...
```

Requires Chrome (headless). Auto-detected on macOS; override with
`CHROME=/path/to/chrome`.

## The loop

1. Write `deck.json`.
2. `deck-shader deck.json --out out/deck.pptx`
3. Render one page and **look at it** before delivering:
   `soffice --headless --convert-to pdf --outdir out out/deck.pptx` then
   `pdftoppm -r 96 -png out/deck.pdf out/p`.
4. Change one number. Repeat.

Never claim the deck is good without step 3. The whole point of a code deck is
that you can check it.

## deck.json

Canvas is **1280 × 720**. 1 px = 0.75 pt, 1 in = 96 px.

```json
{
  "preset": {"light": "#ffc98a", "origin": [0.55, 0.85], "dir": [-0.42, -1.0], "intensity": 1.0},
  "slides": [
    {
      "time": 2.0,
      "notes": "speaker note",
      "elements": [
        {"type": "text", "x": 72, "y": 44, "w": 600, "text": "§ 01",
         "sizePt": 10, "color": "#6B7078", "font": "Menlo"},
        {"type": "rect", "x": 72, "y": 176, "w": 1136, "h": 1, "fill": "#D8DEE4"},
        {"type": "image", "src": "assets/band.jpg", "x": 1100, "y": 0, "w": 108, "h": 658}
      ]
    }
  ]
}
```

| element | fields |
|---|---|
| `text` | `x y w h`, `paragraphs[]` → `runs[]`; per run `text sizePt color font bold spc` |
| `rect` | `x y w h`, `fill` or `stroke:{color,widthPt}` — this is how hairlines are made |
| `image` | `src` (relative to the deck file), `x y w h` |

Per slide: `background` (`"#FCFBF9"` solid, `"bg.png"` picture, omit → shader
render), `time` (shader time), `notes`.

`preset` fields: `light` `origin` `dir` `intensity` — plus `width` (beam
thickness), `haze` (dust), `floor` (reflection), `horizon`, `grain`. Shipped
presets: `cinematic`, `editorial`, `signal`, `glass`, `dawn`
(`--preset <name>` overrides the JSON). Instead of the object you may write
`"preset": "glass"` — top-level or per slide.

`examples/precision/deck.json` is the reference. `examples/hello/` is the
minimal one.

## Rules that keep it from looking generated

- One light per deck; the shader is for 1–2 stage pages, not behind body copy.
- Margins 72, structure lines 1px, and reuse those numbers on every page.
- One accent per page. Two accents reads as none.
- ≤ 5 lines per slide.
- Speaker notes are not optional.

## What NOT to do

- Don't add `roundrect`, shadows, gradient fills, or a title underline. The
  renderer doesn't have them on purpose.
- Don't put a shader background under a dense text page — unreadable.
- Don't hand-place text without rendering and looking. Coordinates that look
  fine in JSON collide on screen.

## Verifying your own output

```bash
deck-shader deck.json --pages 1 --png-only     # background only, fast
deck-shader deck.json --out out/deck.pptx
```

Unchanged backgrounds are cached, so the change-one-number loop is ~0.1 s per
run. If you edit `template.html` the cache invalidates itself; `--no-cache`
forces a full re-render.
