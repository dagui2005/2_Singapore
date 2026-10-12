"""
分析 2026-10-06 ~ 2026-10-07 跨夜 SpeedBand 拥堵变化
====================================================
- 输入: Dynamic_2026_03_16/realtime_monitoring/TrafficSpeedBands_*.json
- 输出: 每个时间片的拥堵指标 + 文本趋势表
"""
import os
import json
import re
from datetime import datetime
from collections import Counter, defaultdict

MONITOR_DIR = r"d:/Luan/2026-05/2_Singapore/Dynamic_2026_03_16/realtime_monitoring"

# 找所有 10/06 ~ 10/07 的文件
pattern = re.compile(r"TrafficSpeedBands_(\d{8})_(\d{6})\.json$")
files = []
for fn in os.listdir(MONITOR_DIR):
    m = pattern.match(fn)
    if m and m.group(1) in ("20261006", "20261007"):
        ts = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        files.append((ts, os.path.join(MONITOR_DIR, fn)))
files.sort()

print(f"找到 {len(files)} 个时间片\n")
print(f"{'时间':<20}{'路段数':>10}{'均值SB':>10}{'SB=1畅通%':>12}{'SB=4拥堵%':>12}{'SB=5极堵%':>12}{'文件大小':>12}")
print("-" * 90)

rows = []
for ts, path in files:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    records = data.get('value', [])
    n = len(records)

    # SpeedBand 分布
    bands = [int(r.get('SpeedBand', 0)) for r in records]
    cnt = Counter(bands)

    # 均值（SpeedBand 越小越畅通，越大越拥堵；8=开放高速不计入均值）
    valid = [b for b in bands if b in (1, 2, 3, 4, 5)]
    mean_sb = sum(valid) / len(valid) if valid else 0

    # 拥堵占比（SB = 4 拥堵 + SB = 5 极堵）
    congested_pct = (cnt.get(4, 0) + cnt.get(5, 0)) / n * 100
    very_bad_pct = cnt.get(5, 0) / n * 100
    free_pct = cnt.get(1, 0) / n * 100

    size_mb = os.path.getsize(path) / 1024 / 1024
    rows.append({
        'ts': ts,
        'n': n,
        'mean_sb': mean_sb,
        'free_pct': free_pct,
        'congested_pct': congested_pct,
        'very_bad_pct': very_bad_pct,
        'sb_dist': dict(cnt),
        'size_mb': size_mb,
    })

    print(f"{ts.strftime('%Y-%m-%d %H:%M'):<20}{n:>10,}{mean_sb:>10.3f}"
          f"{free_pct:>11.2f}%{congested_pct:>11.2f}%{very_bad_pct:>11.2f}%"
          f"{size_mb:>10.1f}MB")

# ============================================================
# 关键观察
# ============================================================
print("\n" + "=" * 90)
print("关键观察：")
worst = max(rows, key=lambda r: r['congested_pct'])
best = min(rows, key=lambda r: r['congested_pct'])
print(f"  最堵时刻: {worst['ts'].strftime('%H:%M')} — 拥堵占比 {worst['congested_pct']:.2f}%, 均值 SB={worst['mean_sb']:.3f}")
print(f"  最畅通时刻: {best['ts'].strftime('%H:%M')} — 拥堵占比 {best['congested_pct']:.2f}%, 均值 SB={best['mean_sb']:.3f}")

# 跨夜趋势
print("\n  跨夜趋势（拥堵占比%）：")
times = " ".join(f"{r['ts'].strftime('%H:%M'):>5}" for r in rows)
congs = " ".join(f"{r['congested_pct']:>5.2f}" for r in rows)
print(f"  时间: {times}")
print(f"  拥堵: {congs}")

# 简单的 ASCII 柱状图
print("\n  拥堵占比柱状图（每个 ▇ = 2%）：")
for r in rows:
    bar = '█' * int(r['congested_pct'] / 2)
    print(f"  {r['ts'].strftime('%H:%M')} {r['congested_pct']:>5.2f}% {bar}")

# ============================================================
# 按 RoadCategory 分层对比最堵 vs 最畅通
# ============================================================
print("\n" + "=" * 90)
print(f"按道路等级分层（对比 {worst['ts'].strftime('%H:%M')} 最堵 vs {best['ts'].strftime('%H:%M')} 最畅通）：")


def by_roadcat(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    records = data.get('value', [])
    grp = defaultdict(lambda: {'total': 0, 'congested': 0})
    for r in records:
        cat = r.get('RoadCategory', 'NA')
        sb = int(r.get('SpeedBand', 0))
        grp[cat]['total'] += 1
        if sb in (4, 5):
            grp[cat]['congested'] += 1
    return grp


worst_path = [p for t, p in files if t == worst['ts']][0]
best_path = [p for t, p in files if t == best['ts']][0]
worst_grp = by_roadcat(worst_path)
best_grp = by_roadcat(best_path)

print(f"{'RoadCat':<10}{'总路段':>10}{'最堵时刻拥堵%':>15}{'最畅通拥堵%':>15}{'差距':>10}")
print("-" * 60)
all_cats = sorted(set(worst_grp.keys()) | set(best_grp.keys()), key=lambda x: (x == 'NA', x))
for cat in all_cats:
    w_total = worst_grp.get(cat, {'total': 0, 'congested': 0})['total']
    w_cong = worst_grp.get(cat, {'total': 0, 'congested': 0})['congested']
    b_total = best_grp.get(cat, {'total': 0, 'congested': 0})['total']
    b_cong = best_grp.get(cat, {'total': 0, 'congested': 0})['congested']
    if w_total == 0 and b_total == 0:
        continue
    w_pct = w_cong / w_total * 100 if w_total else 0
    b_pct = b_cong / b_total * 100 if b_total else 0
    diff = w_pct - b_pct
    print(f"{cat:<10}{max(w_total, b_total):>10,}{w_pct:>14.2f}%{b_pct:>14.2f}%{diff:>+9.2f}%")

# ============================================================
# 跨夜 SpeedBand 分布演化（每个时间片的 SB 分布）
# ============================================================
print("\n" + "=" * 90)
print("SpeedBand 分布演化（每行一个时间片，单位：%）:")
print(f"{'时间':<10}{'SB=1畅通':>10}{'SB=2缓行':>10}{'SB=3慢行':>10}{'SB=4拥堵':>10}{'SB=5极堵':>10}{'SB=8开放高速':>12}")
print("-" * 70)
for r in rows:
    sd = r['sb_dist']
    n = r['n']
    sb1 = sd.get(1, 0) / n * 100
    sb2 = sd.get(2, 0) / n * 100
    sb3 = sd.get(3, 0) / n * 100
    sb4 = sd.get(4, 0) / n * 100
    sb5 = sd.get(5, 0) / n * 100
    sb8 = sd.get(8, 0) / n * 100
    print(f"{r['ts'].strftime('%H:%M'):<10}{sb1:>9.2f}%{sb2:>9.2f}%{sb3:>9.2f}%{sb4:>9.2f}%{sb5:>9.2f}%{sb8:>11.2f}%")
