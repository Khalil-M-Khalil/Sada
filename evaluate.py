#!/usr/bin/env python3
"""Evidence tool for Sada: measures how well the detector really works on YOUR link.

  python evaluate.py record  [session.csv]   guided 5-minute session on your real adapter
  python evaluate.py report   session.csv    metrics + report.html (same detector as server.py)
  python evaluate.py simulate [session.csv]  SYNTHETIC session, only to test this pipeline

A report built from a simulated file is stamped SIMULATED and must never be shown as a result."""
import csv, random, statistics as st, sys, time
from collections import deque
import server as sv

ZT = ["تحرّك قرب الهاتف", "تحرّك في الوسط", "تحرّك قرب اللابتوب"]
PLAN = [("quiet", 20)]
for _ in range(3):
    for z in range(3):
        PLAN += [("prep", 3), ("zone%d" % z, 8), ("quiet", 8)]
PLAN += [("quiet", 120)]


def save(path, rows, source):
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write("# source=%s\n" % source)
        w = csv.writer(f)
        w.writerow(["t", "rssi", "label"])
        w.writerows(rows)


def load(path):
    with open(path, encoding="utf-8") as f:
        source = f.readline().split("=", 1)[1].strip()
        return source, [(float(t), float(r), l) for t, r, l in list(csv.reader(f))[1:]]


def record(path):
    print("ضع الهاتف واللابتوب في مكانهما النهائي ولا تحرّكهما. تبدأ الجلسة بعد 5 ثوان…")
    time.sleep(5)
    rows = []
    for label, secs in PLAN:
        say = {"quiet": "ابتعد عن الجهازين وابقَ ساكناً", "prep": "استعد…"}.get(label) or ZT[int(label[-1])]
        print(f"[{secs:>3}s] {say}")
        end = time.time() + secs
        while time.time() < end:
            g = sv.read_rssi()
            if g:
                rows.append((round(time.time(), 2), g[0], label))
            time.sleep(0.5)
    save(path, rows, "real adapter")
    print("تم الحفظ:", path)


def simulate(path):
    random.seed(11)
    prof, x, rows, t = {0: (-1.0, 2.0, .8), 1: (-3.5, 3.5, .8), 2: (-1.5, 2.2, .2)}, 0.0, [], 0.0
    for label, secs in PLAN:
        for _ in range(secs * 2):
            if label.startswith("zone"):
                shift, sd, ar = prof[int(label[-1])]
                x = ar * x + (1 - ar) * random.gauss(0, sd) * 1.6
                v = -52 + shift + x + random.gauss(0, .3)
            else:
                x = 0.0
                v = -52 + random.gauss(0, .5)
            rows.append((t, round(v, 2), label))
            t += .5
    save(path, rows, "SIMULATED")


def segments(rows):
    segs, cur = [], None
    for t, _, l in rows:
        if cur and cur[2] == l:
            cur[1] = t
        else:
            cur = [t, t, l]
            segs.append(cur)
    return segs


def replay(rows, sens):
    """Same detector as server.py: baseline from the first quiet block, 3 readings in a row = event."""
    base = []
    for _, r, l in rows:
        if l != "quiet":
            break
        base.append(r)
    mean, std = st.mean(base), max(0.35, st.pstdev(base))
    win, hits, last, ev = deque(maxlen=14), 0, -9, []
    for t, r, _ in rows:
        win.append(r)
        if len(win) < 8:
            continue
        thr, ratio = sv.threshold(sens), sv.motion_ratio(win, mean, std)
        if ratio < 1 + (thr - 1) * .4:
            mean += .01 * (r - mean)
            std = max(.35, std + .01 * (st.pstdev(win) - std))
        hits = hits + 1 if ratio >= thr else 0
        if hits == 3 and t - last > 4:
            ev.append(t)
            last = t
    return ev, len(base) / 2


def metrics(rows):
    segs = segments(rows)
    trials = [s for s in segs if s[2].startswith("zone")]
    busy = [(s[0], s[1] + 6) for s in segs if s[2] in ("zone0", "zone1", "zone2")]  # motion + 6 s of lag
    out = []
    for sens in range(1, 13):
        ev, base_s = replay(rows, sens)
        det = sum(any(s[0] <= e <= s[1] + 3 for e in ev) for s in trials)
        quiet_s = sum(s[1] - s[0] for s in segs if s[2] == "quiet") - base_s
        quiet_s -= 6 * len(trials)  # the 6 s after each motion are not counted as quiet
        fa = sum(1 for e in ev if not any(a <= e <= b for a, b in busy) and e > rows[0][0] + base_s)
        out.append((sens, 100 * det / len(trials), fa, fa / max(quiet_s, 1) * 3600))
    return out, len(trials)


def zones(rows):
    base = []
    for _, r, l in rows:
        if l != "quiet":
            break
        base.append(r)
    mean, by = st.mean(base), {}
    for a, b, l in segments(rows):
        if l.startswith("zone"):
            w = [r for t, r, ll in rows if a <= t <= b]
            vs = [sv.feats(w[i - 8:i], mean) for i in range(8, len(w) + 1)]
            by.setdefault(int(l[-1]), []).append(vs)
    rounds = min(len(v) for v in by.values())
    conf, ok, n = [[0] * 3 for _ in range(3)], 0, 0
    for held in range(rounds):  # leave one whole round out
        mdl = sv.fit({z: [v for i, r in enumerate(by[z]) if i != held for v in r] for z in by})
        for z in by:
            for v in by[z][held]:
                g = sv.predict(v, mdl)[0]
                conf[z][g] += 1
                ok += g == z
                n += 1
    return ok / n, conf, rounds


def report(path):
    source, rows = load(path)
    table, ntr = metrics(rows)
    acc, conf, rounds = zones(rows)
    sim = source != "real adapter"
    maxfa = max(5, max(r[3] for r in table))
    pts = "".join(f'<circle cx="{50 + r[3] / maxfa * 340:.0f}" cy="{230 - r[1] / 100 * 200:.0f}" r="5" fill="#b98cff"/>'
                  f'<text x="{58 + r[3] / maxfa * 340:.0f}" y="{228 - r[1] / 100 * 200:.0f}" fill="#9aaad0" font-size="11">{r[0]}</text>' for r in table)
    trs = "".join(f"<tr><td>{r[0]}</td><td>{r[1]:.0f}%</td><td>{r[2]}</td><td>{r[3]:.1f}</td></tr>" for r in table)
    names = ["near phone", "middle", "near laptop"]
    cm = "".join(f"<tr><th>{names[i]}</th>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for i, row in enumerate(conf))
    banner = '<p style="background:#ff6b57;color:#fff;padding:12px;border-radius:8px"><b>SIMULATED DATA.</b> This only tests the pipeline. These are not real results.</p>' if sim else ""
    html = f"""<!doctype html><meta charset="utf-8"><title>Sada evaluation</title>
<body style="font-family:Segoe UI,sans-serif;max-width:760px;margin:30px auto;background:#0b1322;color:#e8eefc;line-height:1.6">
<h1>Sada: evaluation report</h1>{banner}
<p>Source: <b>{source}</b> · motion trials: <b>{ntr}</b> ({rounds} rounds × 3 zones) · session file: {path}</p>
<h2>Detection vs false alarms, by sensitivity</h2>
<svg width="420" height="260" style="background:#101c34;border-radius:12px"><line x1="50" y1="230" x2="400" y2="230" stroke="#9aaad0"/><line x1="50" y1="30" x2="50" y2="230" stroke="#9aaad0"/>{pts}
<text x="150" y="252" fill="#9aaad0" font-size="11">false alarms per hour (0 to {maxfa:.0f})</text><text x="8" y="24" fill="#9aaad0" font-size="11">detected %</text></svg>
<table border="1" cellpadding="6" style="border-collapse:collapse"><tr><th>sensitivity</th><th>detected</th><th>false alarms</th><th>per hour</th></tr>{trs}</table>
<h2>Which zone (leave-one-round-out)</h2><p>Accuracy: <b>{acc * 100:.0f}%</b> (chance: 33%). {"Usable: clearly above chance." if acc >= 1 / 3 + .25 else "NOT reliable: too close to chance. Do not rely on the zone."}</p>
<table border="1" cellpadding="6" style="border-collapse:collapse"><tr><th>true \\ guessed</th><th>phone</th><th>middle</th><th>laptop</th></tr>{cm}</table>
<h2>Limits</h2><ul><li>One room, one placement of the two devices, one person walking.</li><li>{ntr} trials is a small sample: treat percentages as rough.</li><li>False alarms per hour come from only a few minutes of quiet time.</li></ul></body>"""
    out = path.rsplit(".", 1)[0] + "_report.html"
    open(out, "w", encoding="utf-8").write(html)
    print("detection / false alarms per hour by sensitivity:", [(r[0], round(r[1]), round(r[3], 1)) for r in table])
    print(f"zone accuracy: {acc:.0%}  ->  {out}")


if __name__ == "__main__":
    cmd, arg = (sys.argv[1:] + [None, None])[:2]
    path = arg or "session.csv"
    {"record": record, "simulate": simulate, "report": report}.get(cmd, lambda p: print(__doc__))(path)
