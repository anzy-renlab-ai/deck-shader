# Changelog

## Unreleased

- `"preset": "glass"` — a preset can be named instead of spelled out, at the
  top level or on one slide. A name that doesn't exist is an error; it used to
  fall back to the default light without saying anything.
- `preset` that isn't a name or an object is rejected with the page number.
- `--png` runs the flat-frame check too. It was only run on the JPEG path, so
  the lossless output could hand you a solid-colour slide.
- Text placed entirely outside the 1280×720 canvas now warns. Images and rects
  bleeding off the edge are still silent — that's a normal bleed.
- A `run` with only `text` no longer crashes. Size, colour and font fall back to
  the element's, then to the same defaults the shorthand `text` form uses.
- Backgrounds are cached in `.deck-shader-cache/` next to the output, keyed on
  the shader config plus a hash of `template.html`. Re-rendering a deck after
  touching one slide is 0.1 s instead of 2.9 s, and the cached plate is
  byte-identical to a fresh render. `--no-cache` re-renders everything.

## 0.2.0

Backgrounds are now 11× smaller, presets are physical parameters instead of
colors, and the tool says out loud when it is about to produce something wrong.

**Output**

- Backgrounds default to JPEG (q92, chroma 4:4:4): **3.4 MB deck → 0.3 MB**, a
  1920×1080 plate goes from 1.7 MB to ~150 KB. `--png` keeps the old lossless
  behaviour, `--quality` changes the dial. Needs Pillow; without it the renderer
  falls back to Chrome's own JPEG writer.
- Backgrounds for a deck render in parallel (4 at a time), so a 10-slide deck is
  wall-clock closer to one page than ten.

**Presets**

- The shader takes `width`, `haze`, `floor`, `horizon` and `grain` as uniforms.
  Defaults reproduce 0.1.0 pixel for pixel.
- Shipped presets are now five, and differ physically: `cinematic`, `editorial`,
  `signal`, plus the two promised ones, `glass` and `dawn`.

**Input**

- `elements` are validated before anything renders: a bad `type`, a missing `x`,
  an `image` without `src`, a `slides` entry that isn't an object — each names
  the page and element index instead of dying in a traceback.
- `style` (font, titleColor, subColor, bodyColor) now actually applies to legacy
  `title`/`sub`/`body` slides. It was being ignored.
- `preset.angle` is accepted as an alias for `preset.dir`.
- `--pages` is rejected without `--png-only` (it used to silently drop slides),
  and out-of-range page numbers say how many pages the deck has.
- Unknown `--preset` lists the ones that exist.

**Runtime**

- Chrome is found on Linux/Windows too (was macOS + a few hardcoded paths).
- A Chrome that returns a flat single-colour frame is an error, not a deck.
- Chrome gets a 90 s timeout instead of hanging forever.
- `--version`.

**Tests**

- `pytest` suite: preset shape, playground/preset drift, every CLI error path,
  and a real render on CI (Ubuntu + Chrome) that asserts the deck opens, the
  text is native, speaker notes survive, backgrounds are under 400 KB, and the
  same deck rendered twice is byte-identical.

## 0.1.0

First release. JSON → WebGL background → `.pptx` with native text, absolute
1280×720 element model, three presets, a browser playground, `SKILL.md`.
