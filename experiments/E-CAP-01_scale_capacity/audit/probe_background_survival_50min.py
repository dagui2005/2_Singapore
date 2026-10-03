import time, os
P = r"D:\Luan\2026-05\2_Singapore\_tmp_probe.txt"
t0 = time.time()
with open(P, "w", encoding="utf-8") as f:
    f.write("probe start pid=%d %s\n" % (os.getpid(), time.strftime("%H:%M:%S")))
    f.flush()
    for i in range(300):          # 300 * 10s = 50 min
        time.sleep(10)
        f.write("tick %-3d %s elapsed=%4.0fs\n" % (i, time.strftime("%H:%M:%S"), time.time() - t0))
        f.flush()
    f.write("probe end (survived 50 min)\n")
