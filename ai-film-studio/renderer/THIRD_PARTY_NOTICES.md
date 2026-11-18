# Third-party notices

## Lemo-Opuscar capture pipeline

The files in `core/render/`, `core/lib.js`, `core/three/post.js`, and
`backend/app/services/media/audio_sfx.py` are adapted from **Lemo-Opuscar** by
Lemomo (LemoLab):

- Source: https://github.com/lemomo-ai/lemo-opuscar
- Copyright: 2026 Lemomo (LemoLab) and Lemo-Opuscar contributors
- License: MIT (see `LICENSE-MIT.txt`)
- Changes: vendored the headless-browser capture modules and deterministic helpers used by this project; the surrounding film template and orchestration are original to AI Film Studio.

Only MIT-licensed code is vendored. Lemo-Opuscar's Markdown guides, `STYLE.md` files,
and image-generation prompts are CC BY-NC 4.0 and are **not** copied or embedded here.

## Runtime dependencies

- `three` (MIT): WebGL scenes and geometry in the motion template.
- `playwright-core` (Apache-2.0): drives the locally installed Chrome/Chromium.
- Google Chrome or Chromium: installed separately by the user.
- FFmpeg: installed separately by the user.
- `numpy`, `scipy`, and `soundfile` (BSD-3-Clause): procedural audio synthesis.
- `google-cloud-storage` (Apache-2.0): optional cloud publishing.
