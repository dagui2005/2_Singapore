import json
from collections import Counter

# 新版
with open('TrafficFlow_redownload_test.json', 'r', encoding='utf-8') as f:
    new = json.load(f)
new_recs = new['Value']
new_ids = set(r['LinkID'] for r in new_recs)
print('=== 新版 (2026-05) ===')
print(f'总记录: {len(new_recs)}')
print(f'unique LinkID: {len(new_ids)}')

# 旧版
with open('Singapore_OD_MATSim_FinalData/08_TrafficCount/TrafficFlow_Data.json', 'r', encoding='utf-8') as f:
    old = json.load(f)
old_recs = old['Value']
old_ids = set(r['LinkID'] for r in old_recs)
print()
print('=== 旧版 (2025-11) ===')
print(f'总记录: {len(old_recs)}')
print(f'unique LinkID: {len(old_ids)}')

# 日期和小时的分层
new_hours = Counter(f"{r['Date']}|{r['HourOfDate']}" for r in new_recs)
print()
print(f'新版 (Date|Hour) 组合数: {len(new_hours)}')
for k in sorted(new_hours.keys())[:5]:
    print(f'  {k}: {new_hours[k]} 条')

old_hours = Counter(f"{r['Date']}|{r['HourOfDate']}" for r in old_recs)
print(f'旧版 (Date|Hour) 组合数: {len(old_hours)}')
for k in sorted(old_hours.keys())[:5]:
    print(f'  {k}: {old_hours[k]} 条')

# 按 LinkID 聚合
new_by_link = Counter(r['LinkID'] for r in new_recs)
old_by_link = Counter(r['LinkID'] for r in old_recs)
print()
print(f'新版每个 LinkID 的记录数分布: min={min(new_by_link.values())}, max={max(new_by_link.values())}, median={sorted(new_by_link.values())[len(new_by_link)//2]}')
print(f'旧版每个 LinkID 的记录数分布: min={min(old_by_link.values())}, max={max(old_by_link.values())}, median={sorted(old_by_link.values())[len(old_by_link)//2]}')

# 去重后的 LinkID 交集
print()
print(f'新旧 LinkID 交集: {len(new_ids & old_ids)}')
print(f'仅新版有: {len(new_ids - old_ids)}')
print(f'仅旧版有: {len(old_ids - new_ids)}')

# 检查是否是 "日期数 × 2（小时）" 的结构
dates_per_link_new = {}
for r in new_recs:
    lid = r['LinkID']
    if lid not in dates_per_link_new:
        dates_per_link_new[lid] = set()
    dates_per_link_new[lid].add(r['Date'])

date_counts = Counter(len(v) for v in dates_per_link_new.values())
print()
print('新版每个 LinkID 覆盖的日期数分布:')
for d, c in sorted(date_counts.items()):
    print(f'  {d} 天: {c} 个 LinkID')
