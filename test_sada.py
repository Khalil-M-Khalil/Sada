"""Automated checks for the detector and the zone model. Run: python -m unittest -v
They use simulated signals, so they prove the code behaves as designed, not that it is accurate on your room
(use evaluate.py for that)."""
import json, os, queue, random, sqlite3, tempfile, threading, time as T, unittest
import server as sv

REAL_SLEEP = T.sleep


class Rig:
    """Runs server.loop on a virtual clock fed by a fake signal."""
    def __init__(self, profiles):
        sv.RUN[0] = False; REAL_SLEEP(.1); sv.RUN[0] = True  # stop any loop left over from a previous test
        random.seed(7)
        self.clk, self.mode, self.x, self.drift, self.prof = [1000.0], None, 0.0, 0.0, profiles
        sv.db = sqlite3.connect(":memory:", check_same_thread=False)
        sv.db.execute("create table events(ts real,score real)")
        sv.FPFILE = os.path.join(tempfile.mkdtemp(), "fp.json")
        sv.FP.clear(); sv.MDL[0] = None; sv.S.update(mean=None, cal=None, train=None, acc=None, armed=True)
        sv.win.clear(); sv.zh.clear(); sv.hits[0] = 0; sv.last_ev[0] = 0.0
        self.q = queue.Queue(); sv.clients[:] = [self.q]
        sv.read_rssi = self.rssi
        sv.time = type("C", (), {"time": staticmethod(lambda: self.clk[0]),
                                 "sleep": staticmethod(lambda s: (self.clk.__setitem__(0, self.clk[0] + .5), REAL_SLEEP(.003)))})
        threading.Thread(target=sv.loop, daemon=True).start()

    def rssi(self):
        if self.mode is None:
            return -52 + random.gauss(0, .5) + self.drift, "rssi"
        shift, sd, ar = self.prof[self.mode]
        self.x = ar * self.x + (1 - ar) * random.gauss(0, sd) * 1.6
        return -52 + shift + self.x + random.gauss(0, .3), "rssi"

    def wait(self, sec):
        end = self.clk[0] + sec
        while self.clk[0] < end:
            REAL_SLEEP(.002)

    def msgs(self):
        out = []
        while not self.q.empty():
            out.append(json.loads(self.q.get()))
        return out

    def calibrate(self):
        sv.S["cal"] = {"t0": self.clk[0], "buf": []}; self.wait(17)

    def train_all(self):
        for z in range(3):
            self.mode = z; sv.FP[z] = []; sv.S["train"] = {"zone": z, "t0": self.clk[0]}; self.wait(13)
            self.mode = None; self.wait(6)


DIFFERENT = {0: (-1.0, 2.0, .8), 1: (-3.5, 3.5, .8), 2: (-1.5, 2.2, .2)}
SAME = {0: (-2.0, 2.5, .6), 1: (-2.0, 2.5, .6), 2: (-2.0, 2.5, .6)}


class Detector(unittest.TestCase):
    def test_quiet_room_has_no_alerts_even_with_drift(self):
        r = Rig(DIFFERENT); r.calibrate(); r.msgs()
        for i in range(240):
            r.drift = -0.8 * i / 240; r.wait(1)
        self.assertEqual(sum("ev" in m for m in r.msgs()), 0)

    def test_walking_triggers_an_alert(self):
        r = Rig(DIFFERENT); r.calibrate(); r.msgs()
        r.mode = 1; r.wait(6)
        self.assertGreaterEqual(sum("ev" in m for m in r.msgs()), 1)

    def test_threshold_is_stricter_at_low_sensitivity(self):
        self.assertGreater(sv.threshold(1), sv.threshold(12))


class Zones(unittest.TestCase):
    def test_distinct_zones_are_learned(self):
        r = Rig(DIFFERENT); r.calibrate(); r.train_all()
        self.assertGreaterEqual(sv.S["acc"], 0.6)

    def test_identical_zones_are_reported_as_unreliable(self):
        r = Rig(SAME); r.calibrate(); r.train_all()
        self.assertLess(sv.S["acc"], 1 / 3 + .25)  # the UI refuses to show a confident position


if __name__ == "__main__":
    unittest.main()
