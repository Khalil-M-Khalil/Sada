# Sada (صدى): Wi-Fi motion sensing on one Windows laptop

**بالعربي:** أداة تكشف الحركة من تغيّر قوة إشارة الواي فاي بين هاتفك (نقطة اتصال) ولابتوبك، بدون أي قطعة إضافية. تعرض الحركة في مشهد ثلاثي الأبعاد، وتقدّر منطقة الحركة من ثلاث مناطق بعد تدريبها منك، وتقيس دقتها بنفسها وتقول «غير مؤكد» عندما لا تستطيع التمييز.

Software only: Python 3 standard library + one HTML page. No extra hardware, no accounts, no cloud. Everything stays on your machine.

## How it measures
1. A phone hotspot is the transmitter; the laptop is the receiver.
2. Every ~0.5 s the laptop reads the signal strength (`netsh wlan show interfaces`).
3. After a 15 s calibration of the still room, it compares current fluctuation with the calm baseline. Three readings in a row above the sensitivity threshold = motion.
4. It follows slow drift while the room is quiet, so heating or a moved cable does not raise false alarms.

## Where is the motion? (and what it cannot know)
One link gives one number, so position cannot be computed from physics. Sada learns it instead: you move for 12 s in each of three zones (near phone / middle / near laptop), it stores a "fingerprint" of each, and classifies new motion by the closest one. It then **measures its own accuracy** with a time-ordered cross-check. If accuracy is not at least 25 points above chance, the UI says the position is not reliable.

## Quick start (Windows 10/11, Python 3.9+)
```
python server.py        # or double-click run.bat
```
Connect the laptop to the phone hotspot, press "calibrate", keep the room still for 15 s, then switch protection on. Keep the phone fixed and do not touch it. Opening `index.html` directly shows a simulation (labelled as such).

## Measure it yourself
```
python evaluate.py record session.csv     # ~5 minute guided session on your real link
python evaluate.py report session.csv     # detection vs false alarms per sensitivity + zone confusion matrix
```
`evaluate.py report` replays the **same detector** the server uses. `evaluate.py simulate` makes a synthetic file only to test the pipeline; its report is stamped SIMULATED.

## Results
_Not measured yet. Run `evaluate.py` on your own link and paste the numbers here (trials, detection rate, false alarms per hour, zone accuracy, room and device placement). Do not publish numbers from `simulate`._

## Limits
- Coarse: three zones, not coordinates. It cannot count people or tell people from pets.
- Accuracy depends on the room and on devices staying fixed; re-calibrate and re-train after moving anything.
- Windows 10 may expose only signal percent, which is coarser than dBm (the UI says so).
- Without CSI hardware (for example an ESP32) detail is limited. That comparison is future work.

## Privacy
Wi-Fi sensing can reveal that people are present without a camera. Use it only on your own network and in your own space, with everyone's knowledge. The server listens on 127.0.0.1 only and rejects requests from other web pages.

## Tests
`python -m unittest -v`: five checks on simulated signals (no alerts in a quiet drifting room, alert on walking, threshold order, zones learned, identical zones flagged unreliable). They prove the code behaves as designed, not that it is accurate in your room.

## Build the .exe and the installer
1. `build_exe.bat` makes `dist\\Sada.exe` with the Sada icon. The packaged app keeps its data in `%APPDATA%\\Sada`.
2. Install [Inno Setup](https://jrsoftware.org/isinfo.php) (free), open `installer.iss`, press Compile. It writes `installer\\Sada-Setup.exe`.
3. Logo files are in `brand/`; `python brand/make_brand.py` regenerates them (needs Pillow).
Unsigned installers trigger a Windows SmartScreen warning; code signing is not set up.

## Not done yet
System-tray icon, alert schedule, history by hour/day/week, English interface, CSI experiment.

## License
MIT. Replace `<your name>` in `LICENSE`.
