# REA Home "Inside your home": local copy

Mirror of https://0xcodila.com/rea-home/inside/ (and /rea-home/), taken 2026-10-23.

Serve from `site/` so the absolute `/rea-home/...` paths resolve:

    cd site && python3 -m http.server 8000
    open http://127.0.0.1:8000/rea-home/inside/          # device list + figure
    open http://127.0.0.1:8000/rea-home/inside/#washer   # deep link to one device

Devices in page order (anchor = id): router, tv, fridge, vacuum, printer, tvbox,
microwave, washer, speaker. Each figure is a self-contained iframe at
`site/rea-home/inside/figures/<id>.html`. `ac.html` is a placeholder on the live
site too and is not listed on the page.

Music: the site has no audio file. Its "Sound: Lofi" toggle synthesises a 74 BPM
lofi loop live with WebAudio (lab-*.js). `music/music-60s.wav` / `.mp3` is that
same synth code rendered offline (61 s, 4 s fade-out from 57 s, -16.5 LUFS).
`music/render-music.html` + `render-server.py` re-render it in a browser.

Not mirrored (not needed for viewing): `/api/v` visit stats (POST, fails locally,
harmless) and the tesseract OCR worker from cdn.jsdelivr.net used only by the
"snap a label" camera feature.
