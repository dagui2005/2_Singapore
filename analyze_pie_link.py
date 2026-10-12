"""
追踪 PAN ISLAND EXPRESSWAY (PIE) 某段路在 13 个时间片的 SpeedBand 变化
"""
import os
import json
import re
from datetime import datetime

MONITOR_DIR = r"d:/Luan/2026-05/2_Singapore/Dynamic_2026_03_16/realtime_monitoring"

# SpeedBand 含义
SB_MEANING = {
    0: '无效/缺失',
    1: '>65 km/h 畅通',
    2: '40-65 缓行',
    3: '20-40 慢行',
    4: '10-20 拥堵',
    5: '<10 极堵',
    6: '未明等级 6',
    7: '未明等级 7',
    8: '>=70 开放高速',
}

# 找所有 10/06 ~ 10/07 的文件
pattern = re.compile(r"TrafficSpeedBands_(\d{8})_(\d{6})\.json$")
files = []
for fn in os.listdir(MONITOR_DIR):
    m = pattern.match(fn)
    if m and m.group(1) in ("20261006", "20261007"):
        ts = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        files.append((ts, os.path.join(MONITOR_DIR, fn)))
files.sort()

# ============================================================
# 第一步：从第一个文件找 PAN ISLAND EXPRESSWAY 的 link
# ============================================================
print("=" * 100)
print("第一步：在第一个文件里找 PIE 高速 link（精确匹配 'PAN ISLAND EXPRESSWAY'）\n")

with open(files[0][1], 'r', encoding='utf-8') as f:
    first_data = json.load(f)

pie_links = []
seen = set()
for r in first_data['value']:
    rn = r.get('RoadName', '').upper()
    if 'PAN ISLAND EXPRESSWAY' in rn and r['LinkID'] not in seen:
        pie_links.append(r)
        seen.add(r['LinkID'])

print(f"PAN ISLAND EXPRESSWAY 路段数: {len(pie_links)}")
print(f"这些路段的 RoadCategory 分布:")
from collections import Counter
cat_cnt = Counter(r['RoadCategory'] for r in pie_links)
for cat, c in cat_cnt.items():
    print(f"  RoadCategory={cat}: {c} 条")

# 选 5 个路段作为样本（每个 RoadCat 一个）
print()
print(f"前 10 个候选路段：")
print(f"{'LinkID':<12}{'RoadName':<30}{'RoadCat':<10}{'SpeedBand':<12}{'Min-Max':<15}")
print("-" * 80)
for r in pie_links[:10]:
    mn = r.get('MinimumSpeed', 'N/A')
    mx = r.get('MaximumSpeed', 'N/A')
    print(f"{r['LinkID']:<12}{r['RoadName']:<30}{r['RoadCategory']:<10}{r['SpeedBand']:<12}{mn}-{mx:<15}")

# 选前 3 个不同 LinkID 做样本
sample_ids = [pie_links[i]['LinkID'] for i in range(3)]
sample_info = []
for sid in sample_ids:
    for r in pie_links:
        if r['LinkID'] == sid:
            sample_info.append({'id': sid, 'name': r['RoadName'], 'cat': r['RoadCategory']})
            break

print()
print(f">>> 选定 {len(sample_ids)} 个 PIE 高速样本路段")
for s in sample_info:
    print(f"    LinkID={s['id']}, RoadCat={s['cat']}, {s['name']}")

# ============================================================
# 第二步：在 13 个文件里追踪这些 link 的 SB
# ============================================================
print()
print("=" * 100)
print("第二步：跟踪这 3 个 link 在 13 个时间片的 SpeedBand\n")

for s in sample_info:
    sid = s['id']
    print("=" * 100)
    print(f"LinkID={sid}, RoadCat={s['cat']}, {s['name']}\n")
    print(f"{'时间':<20}{'SB':<5}{'含义':<20}{'Min-Max':<15}{'趋势':<10}")
    print("-" * 80)

    trace = []
    for ts, path in files:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        hit = None
        for r in data['value']:
            if r['LinkID'] == sid:
                hit = r
                break
        if hit:
            sb = int(hit['SpeedBand'])
            mn = hit.get('MinimumSpeed', 'N/A')
            mx = hit.get('MaximumSpeed', 'N/A')
            meaning = SB_MEANING.get(sb, '?')
            trace.append({'ts': ts, 'sb': sb, 'min': mn, 'max': mx})
            print(f"{ts.strftime('%Y-%m-%d %H:%M'):<20}{sb:<5}{meaning:<20}{mn}-{mx:<15}")

    if not trace:
        continue

    # 趋势总结
    sbs = [t['sb'] for t in trace]
    sb_set = set(sbs)
    print(f"\n  统计：min={min(sbs)}, max={max(sbs)}, 均值={sum(sbs)/len(sbs):.2f}, 不同值={sorted(sb_set)}")
    if len(sb_set) == 1:
        print(f"  >>> 🚨 SpeedBand 13 个时间片**完全不变** = {sbs[0]} ({SB_MEANING.get(sbs[0], '?')})")
    else:
        # 看变化点
        transitions = []
        for i in range(1, len(trace)):
            if trace[i]['sb'] != trace[i-1]['sb']:
                transitions.append((trace[i-1]['ts'].strftime('%H:%M'), trace[i-1]['sb'], trace[i]['ts'].strftime('%H:%M'), trace[i]['sb']))
        print(f"  >>> 变化次数: {len(transitions)}")
        for t in transitions:
            print(f"      {t[0]}({t[1]}) -> {t[2]}({t[3]})")

    # 时间序列 ASCII
    print(f"\n  跨夜 SpeedBand 演化图：")
    for t in trace:
        sb = t['sb']
        # 用柱子表示拥堵程度（SB 越大越堵）
        bar_len = max(1, sb * 3) if sb <= 8 else 5
        bar = '█' * bar_len
        label = SB_MEANING.get(sb, '?')
        print(f"    {t['ts'].strftime('%H:%M')}  SB={sb} [{label:<15}] {bar}")
    print()

# ============================================================
# 第三步：横向对比 — PIE 高速跨夜变化最大的 5 条 link
# ============================================================
print("=" * 100)
print("第三步：横向对比 — PIE 高速跨夜变化幅度 Top 10\n")

# 追踪前 50 个 link
N = 50
target_ids = [pie_links[i]['LinkID'] for i in range(min(N, len(pie_links)))]
traces = {lid: [] for lid in target_ids}
id_to_name = {pie_links[i]['LinkID']: pie_links[i]['RoadName'] for i in range(min(N, len(pie_links)))}

for ts, path in files:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    by_id = {r['LinkID']: int(r['SpeedBand']) for r in data['value']}
    for lid in target_ids:
        traces[lid].append(by_id.get(lid))

print(f"{'LinkID':<12}{'RoadName':<30}{'min':>5}{'max':>5}{'range':>7}{'不同值数':>10}")
print("-" * 80)
results = []
for lid in target_ids:
    sbs = [s for s in traces[lid] if s is not None]
    if not sbs:
        continue
    rng = max(sbs) - min(sbs)
    var = len(set(sbs))
    results.append({'id': lid, 'name': id_to_name[lid], 'min': min(sbs), 'max': max(sbs), 'range': rng, 'var': var, 'sbs': sbs})

results.sort(key=lambda x: -x['range'])
for r in results[:10]:
    print(f"{r['id']:<12}{r['name']:<30}{r['min']:>5}{r['max']:>5}{r['range']:>7}{r['var']:>10}")

print(f"\n>>> 变化最大的 PIE link (Top 3) 的 13 个时间片 SpeedBand 序列:")
for r in results[:3]:
    sbs = r['sbs']
    print(f"  LinkID={r['id']}: {' -> '.join(str(s) for s in sbs)}")
