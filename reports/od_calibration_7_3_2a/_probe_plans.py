import gzip
import re

p = r"D:\Luan\2026-05\2_Singapore\reports\matsim_assignment_6_3_3b\lambda_0p050\ITERS\it.0\step6_3_3b_lambda_0p050.0.plans.xml.gz"
n_p = n_r = multi = 0
samples = []
with gzip.open(p, "rt", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if "<person " in line and "id=" in line:
            n_p += 1
        if "<route" in line and 'type="links"' in line:
            n_r += 1
            if len(line) > 500:
                multi += 1
            if len(samples) < 2:
                samples.append(line.strip()[:400])
        if i > 3_000_000:
            break
out = [f"persons={n_p} routes={n_r} long_lines={multi}"] + samples
open(r"D:\Luan\2026-05\2_Singapore\reports\od_calibration_7_3_2a\_tmp_header.txt", "w", encoding="utf-8").write("\n\n".join(out))
