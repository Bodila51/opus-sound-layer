# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "soundfile", "matplotlib"]
# ///
"""Find, cut, clean and judge sound effects. Needs ffmpeg on PATH.

  sfx.py kit [--manifest kit.json] [--out audio/kit]
      Download the pinned CC0 starter kit and prepare every sound.
  sfx.py search "laptop key press" --type key [--n 6] [--out audio/candidates]
      Search CC0 recordings on Freesound through Openverse (no key), download,
      prepare and judge them. Prints one verdict line per file.
  sfx.py analyze FILE [FILE ...] --type key [--out audio/sfx]
      Prepare and judge local files.

Prepare = cut to the strongest event, high-pass, low-pass, 5 ms fades,
mono, 48 kHz, peak at -3 dBFS. Judge = reject boomy (>50% energy below
150 Hz), hissy (>40% above 6 kHz), noise-like (spectral flatness) and noisy
floors. Every prepared file gets a .json sidecar with its measurements.
"""
import argparse, json, os, subprocess, sys, urllib.parse, urllib.request
import numpy as np
from scipy import signal
import soundfile as sf

SR = 48000
UA = "sound-layer/1.0 (motion video sound design)"

# win: (min_s, max_s) length of the kept event. kind: transient | swell | tonal
TYPES = {
    "click":  dict(kind="transient", win=(0.05, 0.15), hp=200, lp=11000),
    "key":    dict(kind="transient", win=(0.05, 0.15), hp=200, lp=11000),
    "tick":   dict(kind="transient", win=(0.03, 0.12), hp=300, lp=12000, hi_max=0.55),
    "pop":    dict(kind="transient", win=(0.06, 0.30), hp=150, lp=11000),
    "tap":    dict(kind="transient", win=(0.06, 0.40), hp=120, lp=10000),
    "thump":  dict(kind="transient", win=(0.15, 0.90), hp=35,  lp=8000, allow_low=True),
    "paper":  dict(kind="swell",     win=(0.15, 0.50), hp=200, lp=11000, noise_ok=True),
    "swish":  dict(kind="swell",     win=(0.20, 0.55), hp=180, lp=10000, noise_ok=True),
    "whoosh": dict(kind="swell",     win=(0.30, 0.90), hp=150, lp=10000, noise_ok=True),
    "chime":  dict(kind="tonal",     win=(0.30, 1.80), hp=200, lp=12000),
}


def load(path):
    """Decode any audio file to mono float32 at 48 kHz with ffmpeg."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def envelope(y, win_s=0.004):
    n = max(1, int(win_s * SR))
    return np.sqrt(np.convolve(y * y, np.ones(n) / n, mode="same"))


def cut_event(y, t):
    """Keep only the strongest event of the file. Never pad into neighbouring
    audio: a short real sound stays short."""
    hi_len = int(t["win"][1] * SR)
    if t["kind"] == "swell":
        env = envelope(y, 0.02)
        p = int(np.argmax(env)); thr = env[p] * 0.1
        a = b = p
        # grow towards the louder side until both edges are 20 dB down
        while b - a < hi_len:
            left = env[a - 1] if a > 0 else 0.0
            right = env[b + 1] if b < len(y) - 1 else 0.0
            if left <= thr and right <= thr: break
            if left >= right: a -= 1
            else: b += 1
    else:
        fine = envelope(y, 0.002)      # onset
        smooth = envelope(y, 0.015)    # tail and second hits, smooth over low cycles
        p = int(np.argmax(fine)); ps = smooth[p]
        a = p
        while a > 0 and fine[a] > fine[p] * 0.1 and p - a < int(0.05 * SR): a -= 1
        a = max(0, a - int(0.005 * SR))
        tail = ps * 10 ** (-40 / 20)
        b, low = p, ps
        while b < len(y) - 1 and smooth[b] > tail and b - a < hi_len:
            low = min(low, smooth[b])
            # a second hit: the level climbs well above the lowest point
            # reached since the peak. Stop at that dip.
            if b - p > int(0.01 * SR) and smooth[b] > max(4 * low, 0.1 * ps):
                b = p + int(np.argmin(smooth[p:b])); break
            b += 1
    return y[a:b].copy()


def clean(x, t):
    sos_hp = signal.butter(4, t["hp"], "highpass", fs=SR, output="sos")
    sos_lp = signal.butter(4, min(t["lp"], SR / 2 - 100), "lowpass", fs=SR, output="sos")
    x = signal.sosfilt(sos_lp, signal.sosfilt(sos_hp, x))
    f = min(int(0.005 * SR), len(x) // 4)
    if f > 0:
        x[:f] *= np.linspace(0, 1, f)
        x[-f:] *= np.linspace(1, 0, f)
    pk = np.max(np.abs(x)) + 1e-12
    return x * (10 ** (-3 / 20) / pk)


def measure(x, t):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    fr = np.fft.rfftfreq(len(x), 1 / SR)
    tot = spec.sum() + 1e-20
    env = envelope(x, 0.002)
    p = int(np.argmax(env))
    above10 = np.where(env[:p + 1] >= 0.1 * env[p])[0]
    above90 = np.where(env[:p + 1] >= 0.9 * env[p])[0]
    rise = (above90[0] - above10[0]) / SR * 1000 if len(above10) and len(above90) else 0.0
    # flatness inside the pass band only, with a floor, so filtered-out bins
    # don't drive the geometric mean to zero
    band = spec[(fr >= max(t["hp"], 100)) & (fr <= t["lp"])]
    band = np.maximum(band, band.max() * 1e-6 + 1e-20)
    flat = float(np.exp(np.mean(np.log(band))) / np.mean(band))
    pre = env[: max(1, int(0.003 * SR))]
    env10 = envelope(x, 0.01)
    edge = max(int(0.005 * SR), len(x) // 10)
    db = lambda v: float(20 * np.log10(v / (env10.max() + 1e-12) + 1e-12))
    env30 = envelope(x, 0.03)
    return dict(
        start_db=round(db(env10[:edge].max()), 1),
        end_db=round(db(env10[-edge:].max()), 1),
        spikiness=round(float(env.max() / (env30.max() + 1e-12)), 2),
        dur_s=round(len(x) / SR, 3),
        peak_offset_s=round(p / SR, 4),
        rise_ms=round(float(rise), 1),
        centroid_hz=int((fr * spec).sum() / tot),
        below150=round(float(spec[fr < 150].sum() / tot), 3),
        above6k=round(float(spec[fr > 6000].sum() / tot), 3),
        flatness=round(flat, 3),
        start_floor_db=round(float(20 * np.log10(np.max(pre) / (env[p] + 1e-12) + 1e-12)), 1),
    )


def judge(m, t):
    why = []
    if m["below150"] > 0.5 and not t.get("allow_low"): why.append("boomy")
    if m["below150"] > 0.85: why.append("no body above 150 Hz (inaudible on phones)")
    if m["above6k"] > t.get("hi_max", 0.4): why.append("hissy")
    if m["flatness"] > 0.35 and not t.get("noise_ok"): why.append("noise-like")
    if t["kind"] == "transient" and m["rise_ms"] > 25: why.append("soft attack")
    if t["kind"] == "swell":
        if max(m["start_db"], m["end_db"]) > -12: why.append("no rise and fall (steady noise)")
        if m["spikiness"] > 2.5: why.append("clicks inside")
    else:
        if m["end_db"] > -20: why.append("cut before it decays")
    if m["dur_s"] < t["win"][0] * 0.5: why.append("too short")
    return why


def prepare(src, typ, out_dir, name=None, meta=None):
    t = TYPES[typ]
    x = clean(cut_event(load(src), t), t)
    m = measure(x, t)
    why = judge(m, t)
    os.makedirs(out_dir, exist_ok=True)
    name = name or os.path.splitext(os.path.basename(src))[0]
    dst = os.path.join(out_dir, name + ".wav")
    sf.write(dst, x.astype(np.float32), SR, subtype="PCM_24")
    side = dict(type=typ, file=dst, verdict="ok" if not why else "reject: " + ", ".join(why), **m)
    if meta: side["source"] = meta
    with open(dst[:-4] + ".json", "w") as fh: json.dump(side, fh, indent=1)
    return side


def fetch(url, dst):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as fh:
        fh.write(r.read())


def openverse(query, n):
    q = urllib.parse.urlencode(dict(q=query, license="cc0", source="freesound",
                                    page_size=n, filter_dead="true"))
    req = urllib.request.Request("https://api.openverse.org/v1/audio/?" + q, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["results"]


def line(s):
    return (f"{os.path.basename(s['file']):34s} {s['dur_s']:5.2f}s rise {s['rise_ms']:5.1f}ms "
            f"centroid {s['centroid_hz']:5d}Hz <150 {s['below150']*100:3.0f}% >6k {s['above6k']*100:3.0f}% "
            f"flat {s['flatness']:.2f} -> {s['verdict']}")


def sheet(files, out_png):
    """One row per prepared sound: waveform and spectrogram, for visual review."""
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    files = [f for f in files if f.endswith(".wav")]
    fig, axes = plt.subplots(len(files), 2, figsize=(11, 1.25 * len(files) + 0.4), squeeze=False,
                             gridspec_kw=dict(width_ratios=[1, 2]))
    for row, f in zip(axes, files):
        x, _ = sf.read(f)
        side = json.load(open(f[:-4] + ".json")) if os.path.exists(f[:-4] + ".json") else {}
        t = np.arange(len(x)) / SR
        row[0].plot(t, x, lw=0.5, color="k"); row[0].set_xlim(0, t[-1] if len(t) else 1); row[0].set_yticks([])
        row[0].set_title(f"{os.path.basename(f)}  {side.get('verdict','')}", fontsize=7, loc="left")
        row[1].specgram(x, NFFT=512, Fs=SR, noverlap=384, cmap="magma", vmin=-120)
        row[1].set_ylim(0, 12000); row[1].set_yticks([150, 2000, 6000, 12000]); row[1].tick_params(labelsize=6)
        row[1].set_title(f"centroid {side.get('centroid_hz','?')} Hz  <150 {side.get('below150','?')}  >6k {side.get('above6k','?')}  flat {side.get('flatness','?')}", fontsize=7, loc="left")
    fig.tight_layout(); fig.savefig(out_png, dpi=90); plt.close(fig)
    print(out_png)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("kit"); k.add_argument("--manifest", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "kit.json")); k.add_argument("--out", default="audio/kit")
    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("--type", required=True, choices=TYPES); s.add_argument("--n", type=int, default=6); s.add_argument("--out", default="audio/candidates")
    a = sub.add_parser("analyze"); a.add_argument("files", nargs="+"); a.add_argument("--type", required=True, choices=TYPES); a.add_argument("--out", default="audio/sfx")
    h = sub.add_parser("sheet"); h.add_argument("files", nargs="+"); h.add_argument("--png", default="audio/sheet.png")
    args = ap.parse_args()
    if args.cmd == "sheet":
        sheet(args.files, args.png); return

    if args.cmd == "kit":
        kit = json.load(open(args.manifest))
        credits = ["# Sound credits", "", "All sounds are CC0 (public domain) from Freesound, found through Openverse.", ""]
        for typ, items in kit["sounds"].items():
            for i, it in enumerate(items):
                raw_dir = os.path.join(args.out, "_raw"); os.makedirs(raw_dir, exist_ok=True)
                raw = os.path.join(raw_dir, f"{typ}-{i+1}.mp3")
                if not os.path.exists(raw): fetch(it["url"], raw)
                side = prepare(raw, typ, os.path.join(args.out, typ), f"{typ}-{i+1}", it)
                print(line(side))
                credits.append(f"- {typ}-{i+1}: \"{it['title']}\" by {it['creator']}, {it['license'].upper()}, {it['landing']}")
        with open(os.path.join(args.out, "CREDITS.md"), "w", encoding="utf-8") as fh: fh.write("\n".join(credits) + "\n")
    elif args.cmd == "search":
        res = openverse(args.query, args.n)
        if not res: print("no CC0 results; try other words"); return
        d = os.path.join(args.out, args.type, "_raw"); os.makedirs(d, exist_ok=True)
        for r in res:
            raw = os.path.join(d, f"ov-{r['id'][:8]}.mp3")
            try:
                if not os.path.exists(raw): fetch(r["url"], raw)
                meta = dict(title=r.get("title"), creator=r.get("creator"), license=r.get("license"),
                            url=r.get("url"), landing=r.get("foreign_landing_url"), openverse_id=r["id"])
                print(line(prepare(raw, args.type, os.path.join(args.out, args.type), f"ov-{r['id'][:8]}", meta)), "|", r.get("title"))
            except Exception as e:
                print("skip", r.get("title"), e, file=sys.stderr)
    else:
        for f in args.files:
            print(line(prepare(f, args.type, os.path.join(args.out, args.type))))


if __name__ == "__main__":
    main()
