#!/usr/bin/env python3
"""Sada: senses motion from the Wi-Fi signal of one Windows laptop.
Python 3 standard library only. Everything stays on this machine."""
import base64, json, math, os, queue, re, sqlite3, statistics as st, subprocess, sys, threading, time, webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT, ZONES = 8765, 3
FROZEN = getattr(sys, "frozen", False)  # True inside the packaged .exe
HERE = os.path.join(os.environ.get("APPDATA") or os.path.dirname(sys.executable), "Sada") if FROZEN else os.path.dirname(os.path.abspath(__file__))
os.makedirs(HERE, exist_ok=True)
ASSETS = getattr(sys, "_MEIPASS", HERE)
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
S = {"armed": False, "sens": 6, "snooze": 0.0, "mean": None, "std": 1.0, "cal": None, "gap": 60,
     "train": None, "acc": None}
win, clients, last_alert, last_ev, hits, zh = deque(maxlen=14), [], [0.0], [0.0], [0], deque(maxlen=6)
hz, prev, MDL, RUN = [2.0], [time.time()], [None], [True]
db = sqlite3.connect(os.path.join(HERE, "sada.db"), check_same_thread=False)
db.execute("create table if not exists events(ts real, score real)")
db.execute("delete from events where ts < ?", (time.time() - 60 * 86400,))  # keep 60 days
db.commit()
FPFILE = os.path.join(HERE, "fingerprints.json")
try:
    with open(FPFILE) as f:
        FP = {int(k): v for k, v in json.load(f).items()}
except Exception:
    FP = {}


def read_rssi():
    """(signal in dBm, 'rssi' or 'pct') of the connected network, or None. Any Windows language."""
    try:
        out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True,
                             text=True, errors="ignore", timeout=3, creationflags=NOWIN).stdout
    except Exception:
        return None
    m = re.search(r"rssi\s*:\s*(-\d+)", out, re.I)
    if m:
        return float(m.group(1)), "rssi"
    m = re.search(r":\s*(\d{1,3})\s*%", out)
    return (int(m.group(1)) / 2 - 100, "pct") if m else None


def motion_ratio(win, mean, std):
    """How far the recent signal is from the calm baseline (1 = calm). Shared with evaluate.py."""
    w = list(win)
    return max(st.pstdev(w) / std, 1 + abs(st.mean(w[-4:]) - mean) / (2 * std))


def threshold(sens):
    return max(1.15, 4.0 - 0.26 * sens)


# ---- where inside the link: fingerprints learned from the user, scored honestly ----
def feats(w, base):
    d = [abs(b - a) for a, b in zip(w, w[1:])]
    return [st.pstdev(w), max(w) - min(w), st.mean(w) - base, min(w) - base, max(w) - base, st.mean(d)]


def fit(fp):
    rows = [v for vs in fp.values() for v in vs]
    mu = [st.mean(c) for c in zip(*rows)]
    sd = [max(1e-6, st.pstdev(c)) for c in zip(*rows)]
    norm = lambda v: [(x - m) / s for x, m, s in zip(v, mu, sd)]
    return norm, {z: [st.mean(c) for c in zip(*map(norm, vs))] for z, vs in fp.items()}


def predict(v, mdl):
    norm, cen = mdl
    x = norm(v)
    w = {z: math.exp(-math.dist(x, c)) for z, c in cen.items()}
    z = max(w, key=w.get)
    return z, w[z] / sum(w.values())


def accuracy():
    """Two-fold cross-check in time order, with a gap so neighbouring windows do not leak."""
    zs = [z for z, vs in FP.items() if len(vs) >= 8]
    if len(zs) < 2:
        return None
    ok = n = 0
    for fold in (0, 1):
        tr, te = {}, {}
        for z in zs:
            vs = FP[z]
            h = len(vs) // 2
            a, b = vs[:h - 1], vs[h + 1:]
            tr[z], te[z] = (a, b) if fold == 0 else (b, a)
        mdl = fit(tr)
        for z in zs:
            for v in te[z]:
                ok += predict(v, mdl)[0] == z
                n += 1
    return ok / n


def refit():
    good = {z: vs for z, vs in FP.items() if len(vs) >= 8}
    MDL[0] = fit(good) if len(good) >= 2 else None
    S["acc"] = accuracy()


def save_fp():
    with open(FPFILE, "w") as f:
        json.dump(FP, f)


def toast(text):
    if os.name != "nt":
        return
    ps = ("Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
          "$n=New-Object System.Windows.Forms.NotifyIcon;$n.Icon=[System.Drawing.SystemIcons]::Warning;"
          "$n.Visible=$true;$n.ShowBalloonTip(6000,'صدى','%s',[System.Windows.Forms.ToolTipIcon]::Warning);"
          "Start-Sleep 7;$n.Dispose()" % text)
    enc = base64.b64encode(ps.encode("utf-16le")).decode()
    subprocess.Popen(["powershell", "-NoProfile", "-EncodedCommand", enc], creationflags=NOWIN)


def loop():
    while RUN[0]:
        t = time.time()
        got = read_rssi()
        r = got[0] if got else None
        hz[0] = 0.85 * hz[0] + 0.15 / max(0.05, t - prev[0])
        prev[0] = t
        msg = {"t": t, "armed": S["armed"], "sens": S["sens"], "snooze": S["snooze"] > t,
               "calibrated": S["mean"] is not None, "hz": hz[0], "gap": S["gap"], "acc": S["acc"],
               "fp": [len(FP.get(i, [])) for i in range(ZONES)]}
        if r is None:
            msg["err"] = "no_wifi"
        else:
            win.append(r)
            msg["rssi"], msg["res"] = r, got[1]
            cal = S["cal"]
            if cal:
                cal["buf"].append(r)
                msg["cal"] = p = min((t - cal["t0"]) / 15, 1)
                if p >= 1 and len(cal["buf"]) > 8:
                    S["mean"], S["std"] = st.mean(cal["buf"]), max(0.35, st.pstdev(cal["buf"]))
                    S["cal"] = None
            elif S["mean"] is not None and len(win) >= 8:
                w8 = list(win)[-8:]
                ratio = motion_ratio(win, S["mean"], S["std"])
                thr = threshold(S["sens"])
                msg.update(ratio=ratio, thr=thr)
                tr = S["train"]
                if tr:  # learning what motion in one zone looks like; no alerts meanwhile
                    p = (t - tr["t0"]) / 12
                    FP.setdefault(tr["zone"], []).append(feats(w8, S["mean"]))
                    msg["train"] = {"zone": tr["zone"], "p": min(p, 1)}
                    if p >= 1:
                        S["train"] = None
                        save_fp()
                        refit()
                else:
                    if ratio < 1 + (thr - 1) * 0.4:  # follow slow drift, only while the room is quiet
                        S["mean"] += 0.01 * (r - S["mean"])
                        S["std"] = max(0.35, S["std"] + 0.01 * (st.pstdev(win) - S["std"]))
                    hits[0] = hits[0] + 1 if ratio >= thr else 0
                    if hits[0] and MDL[0]:
                        zh.append(predict(feats(w8, S["mean"]), MDL[0]))
                        votes = [z for z, _ in zh]
                        z = max(set(votes), key=votes.count)
                        msg["zone"] = z
                        msg["zc"] = st.mean(c for zz, c in zh if zz == z) * votes.count(z) / len(votes)
                    elif not hits[0]:
                        zh.clear()
                    if S["armed"] and hits[0] == 3 and t - last_ev[0] > 4:  # 3 readings in a row
                        last_ev[0] = t
                        msg["ev"] = ratio
                        db.execute("insert into events values(?,?)", (t, ratio))
                        db.commit()
                        if t > S["snooze"] and t - last_alert[0] > S["gap"]:
                            last_alert[0] = t
                            toast("تم رصد حركة")
        data = json.dumps(msg).encode()
        for q in list(clients):
            q.put(data)
        time.sleep(0.5)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def trusted(self):  # blocks other web pages from controlling the tool
        ok = (f"127.0.0.1:{PORT}", f"localhost:{PORT}")
        origin = self.headers.get("Origin")
        return self.headers.get("Host") in ok and (origin is None or origin in tuple("http://" + h for h in ok))

    def do_GET(self):
        if not self.trusted():
            return self.reply(403, b"{}")
        if self.path == "/events":
            q = queue.Queue()
            clients.append(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                while True:
                    try:
                        self.wfile.write(b"data: " + q.get(timeout=15) + b"\n\n")
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except OSError:
                pass
            finally:
                clients.remove(q)
        elif self.path == "/history":
            rows = db.execute("select ts,score from events order by ts desc limit 200").fetchall()
            self.reply(200, json.dumps(rows).encode())
        else:
            with open(os.path.join(ASSETS, "index.html"), "rb") as f:
                self.reply(200, f.read(), "text/html; charset=utf-8")

    def do_POST(self):
        if not self.trusted():
            return self.reply(403, b"{}")
        try:
            c = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except ValueError:
            return self.reply(400, b"{}")
        if "armed" in c:
            S["armed"] = bool(c["armed"])
        if "sens" in c:
            S["sens"] = min(12, max(1, int(c["sens"])))
        if c.get("calibrate"):
            S["cal"], S["train"] = {"t0": time.time(), "buf": []}, None
        if "train" in c and S["mean"] is not None and not S["cal"]:
            z = int(c["train"]) % ZONES
            FP[z] = []
            S["train"] = {"zone": z, "t0": time.time()}
        if c.get("clear_fp"):
            FP.clear()
            S["train"] = None
            save_fp()
            refit()
        if "gap" in c:
            S["gap"] = min(900, max(10, int(c["gap"])))
        if c.get("snooze"):
            S["snooze"] = time.time() + 600
        self.reply(200, b'{"ok":true}')


if __name__ == "__main__":
    refit()
    threading.Thread(target=loop, daemon=True).start()
    url = f"http://127.0.0.1:{PORT}/"
    print("صدى شغّال على", url, "- اضغط Ctrl+C للإيقاف")
    webbrowser.open(url)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
