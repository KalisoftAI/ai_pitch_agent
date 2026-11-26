# Kalika AV refinement pack

Minimal, source-controlled bridge between GCS evidence and `ai-film-studio` render inputs. No media binaries are copied into git; JSON holds paths, probes, and bindings.

## Abstract

One mapping, three personas, six scenes. GCS transcripts and bundle scripts supply the story; FFmpeg probes and frame sheets supply the visual evidence; the studio supplies the motion/audio contract.

## Sources

| Purpose | Path | Note |
| --- | --- | --- |
| Code bundle | `gs://sales-crm/assets/code-files/Kalika_Enterprise_Complete_AV_Links_CRM_Bundle.zip` | Persona scripts, transcripts, CRM, account links |
| Audio/transcript bundle | `gs://sales-crm/assets/code-files/Kalika_Enterprise_Audio_Transcripts_CRM_Bundle.zip` | Same AV/CRM data without the external directory |
| Audio files | `gs://sales-crm/assets/Audio-files/` | Actual prefix is plural `Audio-files` |
| Manufacturing video | `gs://sales-crm/Manufacturing-Data/kalika-videos/manufacturing/` | Includes `Workshop-1/`, `Workshop-2/` |
| Brand images/video | `gs://kalika_enterprises/images and videos/` | Actual prefix is `images and videos`, not `images/` |

## Evidence method

1. `ffprobe` for duration, dimensions, fps, bytes, codec, sample rate, channels.
2. FFmpeg frame probes at 10%, 50%, 90% plus `3x1` contact sheets under `C:\Users\user\AppData\Local\Temp\opencode\kaliflow\frames\`.
3. Transcript duration matching, bundle script timing, OCR, filename semantics, and GCS MD5/SHA-256 duplicate checks.
4. Human visual review is still required before publishing; image inspection in this run was not available, so tentative rows are marked `low` confidence in JSON.

Frame probe template:

```powershell
ffmpeg -ss "{0.10 * duration}" -i "clip.mp4" -frames:v 1 -q:v 2 "frame.jpg"
ffmpeg -i "clip.mp4" -vf "fps=3/duration,scale=480:-1,tile=3x1" -frames:v 1 "sheet.jpg"
```

## Persona map

| Persona | Audio stem | Video evidence | Studio style / scene pattern focus |
| --- | --- | --- | --- |
| A — MIDC procurement | `mix01_MIDC_Procurement_Persona_30s.wav` | Blown film, size change, Kaliflow OEE | `documentary` → `infographic` → `data` → `quote` |
| B — Distributor / dairy-agro | `mix02_Distributor_HighYield_Persona_25s.wav` | XHD cast, high-speed winder, pigmented roll | `split` → `infographic` → `walkthrough` → `quote` |
| C — Export / ESG circular | `mix03_Export_ESG_Circular_Persona_25s.wav` | Granule ASMR, grinder, seaworthy proof | `isometric` → `data` → `documentary` → `quote` |

## Flow diagram

```text
GCS buckets
  code-files zips ── scripts / transcripts / CRM ──┐
  Audio-files ── ffprobe / LUFS / duplicates ──────┤
  manufacturing + images/video ── FFmpeg frames ──┤
                                                    v
                                     refined-mapping.json
                                     stats-and-insights.json
                                                    v
                              script → storyboard → render options
                              (style, patterns, palette, audio mix)
                                                    v
                                  preview → human review → publish
                                                    v
                    marketing-videos/renders/{project}/{job}/export.mp4
```

## Architecture breakdown

| Layer | Input | Output | Studio contract |
| --- | --- | --- | --- |
| Source | GCS prefixes above | Verified object paths | `gcs_service.py` naming rules |
| Probe | Video/audio objects | Duration, fps, dimensions, LUFS, duplicates | `ffprobe -show_streams -of json` |
| Frame | Manufacturing clips | 10/50/90% sheets | `ffmpeg` + `tile=3x1` |
| Mapping | Scripts, transcripts, probes | Persona/asset bindings | `refined-mapping.json` |
| Insights | CRM workbook/CSV/JSON | Segment, tier, product, gaps | `stats-and-insights.json` |
| Story | Persona bindings | 6-scene plan | `POST /script/generate`, `/storyboard/generate` |
| Render | Scene plan + patterns | Preview/export MP4 | `RenderCreate.scene_patterns` |
| Audio | Stem + mux config | Loudness-normalised AAC | `audio_mixer.py` `-14 LUFS` |

## Minimal design

- Palette: `bg #0B1020`, `panel #14265C`, `ink #E9E4DA`, `signal #3CC4CC`, `accent #FFC727`.
- Six scenes only; last scene always `quote`.
- One source of truth per fact: JSON owns paths and counts, Markdown explains them.
- Collapse exact duplicates; keep one canonical URI per visual.
- Keep binaries out of git; ship only this pack and its ZIP.

## Studio payload

```json
{
  "quality": "both",
  "include_captions": true,
  "engine": "motion",
  "motion_style": "documentary",
  "effects": ["grain", "vignette"],
  "audio": true,
  "scene_patterns": {
    "0": "documentary",
    "1": "infographic",
    "2": "isometric",
    "3": "split",
    "4": "data",
    "5": "quote"
  },
  "template": "default"
}
```

`scene_patterns` keys are zero-based, matching `frontend/src/pages/render.tsx`.

## Stats and insights

- CRM: 112 leads; 44 general trade/distributors, 21 packaging/polymers, 12 dairy/agro/FMCG, 12 services/tech, 10 engineering/industrial.
- 107 direct SME/trade vs 5 Tier-1 enterprise; 87/112 have generic "General Packaging / Film Inquiry" interest.
- 63/112 lack email (56.25%); 21 lack company; 23 lack contact person.
- Manufacturing: 27 media objects plus 2 directory markers; 25 probed; 2 Workshop-2 objects excluded (83 MB and 713 MB).
- Audio: 13 media objects + 1 directory marker; 6 curated stems; 16 transcript segments (`STRIP` 7, `KEEP_BASE_LAYER` 6, `STRIP_AND_DUB` 2, `KEEP_ASMR_LAYER` 1).
- Seven exact duplicate video groups across manufacturing and brand buckets.

## Roadmap

| Phase | Action | Gate |
| --- | --- | --- |
| 0 | Confirm corrected GCS prefixes and bundle versions | Paths resolve |
| 1 | Human visual pass on FFmpeg contact sheets | Tentative rows promoted to high confidence |
| 2 | Seed one project per persona with the 6-scene payload | Script/storyboard approved |
| 3 | Render previews, mux persona stems, compare LUFS | `-14 LUFS` normalized AAC |
| 4 | Publish to `marketing-videos/renders/{project}/{job}/` | Manifest + gallery verified |
| 5 | Feed CRM segment counts into KPI scenes | Stats match raw sheets |

## Files

- `refined-mapping.json` — paths, probes, personas, scene plan, roadmap.
- `stats-and-insights.json` — exact counts, insights, caveats.
- `refinement-pack.zip` — both JSON files plus this README.

## Caveats

- Bundle transcript filenames are not present verbatim in GCS; mappings use duration and scene descriptions.
- Script LUFS/BPM are design targets; measured LUFS values differ and are not compliance verdicts.
- Non-business audio (music, long voice notes, unrelated promos) is inventoried but excluded from personas.
- `base-mc-workshop2-html.mp4` dashboard values are media content, not verified live ERP data.
