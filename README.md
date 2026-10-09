# opus-sound-layer

A sound layer for motion videos made by Claude Opus 5.5 (Remotion, HyperFrames or any renderer that can export frame timings).

Opus can't hear its own audio, so its sound effects come out synthetic and off the picture. This repo gives it real recordings, a mixer that places every sound from the timeline, and a QA script that measures what a sound designer would listen for.

The prompt to paste into Claude Code is in [PROMPT.md](PROMPT.md).

## What's inside

| Script | Does |
|---|---|
| `scripts/sfx.py kit` | Downloads 26 hand-picked CC0 recordings from Freesound (10 types: click, key, tick, tap, thump, pop, whoosh, swish, chime, paper), cuts each to one clean event, filters it and writes `CREDITS.md` |
| `scripts/sfx.py search` | Finds more CC0 recordings through the Openverse API (no key), cuts and judges them: boomy, hissy, steady noise, clicks inside, soft attack |
| `scripts/sfx.py sheet` | Waveform and spectrogram per sound, so Claude can look at what it can't hear |
| `scripts/mix.py` | Builds the mix from one cue sheet: peak-aligned placement, rotating files with ±2% pitch, layered hero hits, per-event gain in each sound's own band against music and voice, ducking, dead stop and filter build before hero hits, −14 LUFS master with a true-peak limiter |
| `scripts/qa.py` | Checks the encoded MP4: each cue against the real picture motion, sync, loudness, true peak, audibility of every sound, music under the voice, dips, silence. Exits 1 on failure |

## Requirements

- [ffmpeg](https://ffmpeg.org) on PATH
- [uv](https://docs.astral.sh/uv/) (installs Python and the packages for each script)

If uv fails with `invalid peer certificate`, set `UV_NATIVE_TLS=1` (common behind antivirus or corporate proxies).

## Run by hand

```bash
uv run scripts/sfx.py kit
uv run scripts/mix.py --schema           # cue sheet format
uv run scripts/mix.py audio/cues.json
ffmpeg -i video.mp4 -i audio/mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest out/final.mp4
uv run scripts/qa.py out/final.mp4
```

## How it was tested

On Windows 11, Python 3.13, ffmpeg 8.1, through `uv run`, with a 15 s test film whose picture and cue sheet come from one timeline:
- a clean run passes every check;
- five deliberately broken versions each fail the right check: audio delayed in the MP4, mix 4 dB too loud, hero cue 6 frames off the picture, no ducking under the voice, effects 25 dB too quiet.


## Licence

Code: MIT. Sounds are not stored here: `sfx.py kit` downloads CC0 (public domain) recordings from Freesound and lists every source in `audio/kit/CREDITS.md`.
