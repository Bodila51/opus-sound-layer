```
SOUND LAYER · Opus 5.5
You can't hear. Use real recordings, place them from the timeline, look at
every sound, and let the QA decide. A human does the final ear check.

SETUP  git clone https://github.com/Bodila51/opus-sound-layer sound-layer
Use its scripts (needs ffmpeg and uv). Never rewrite them and never loosen a
threshold to make a check pass.

1 CUES  Export audio/cues.json from the picture's own timing (springs,
easings, data-start). Never type frames. Format: uv run
sound-layer/scripts/mix.py --schema. Sound only on real actions; tag each:
cut (full-frame change) · move (frame of peak speed) · land (frame motion
stops) · appear (element pops in). One hero per ~4 s (logo, reveal):
"thump+tap" with stop_before and build.

2 SOUNDS  uv run sound-layer/scripts/sfx.py kit  (26 CC0 recordings).
Never synthesize hits, clicks or whooshes; no meme sounds. For a missing
type: sfx.py search "<material action>" --type <type>, then sfx.py sheet
and LOOK: reject two events in one clip, steady noise, clicks inside a
whoosh, clean sine lines on a physical sound. Music: my track, or a CC0 loop.

3 BUILD  Render the picture muted, then:
uv run sound-layer/scripts/mix.py audio/cues.json
ffmpeg -i video.mp4 -i audio/mix.wav -map 0:v -map 1:a -c:v copy -c:a aac
-b:a 256k -shortest out/final.mp4
uv run sound-layer/scripts/qa.py out/final.mp4

4 VERIFY  Fix every FAIL by changing cues or sounds, at most 2 rounds.
Open audio/qa.png and describe what you see at each hero cue.

5 DELIVER  final.mp4 · audio/kit/CREDITS.md · LISTEN.md: 5 timecodes to
check by ear. Don't call the sound good; report what the checks show.
```
