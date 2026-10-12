import json
from collections import Counter

with open('TrafficFlow_redownload_test.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('LastUpdatedDate:', data.get('LastUpdatedDate', 'N/A'))
records = data.get('Value', [])
print(f'总记录数: {len(records)}')

if not records:
    exit()

# HourOfDate 分布
hours = Counter(str(r.get('HourOfDate', 'N/A')) for r in records)
print(f'\nHourOfDate 分布:')
for h in sorted(hours.keys(), key=lambda x: (x == 'N/A', x)):
    print(f'  HourOfDate={h}: {hours[h]} 条')

# Date 分布
dates = Counter(str(r.get('Date', 'N/A')) for r in records)
print(f'\nDate 分布 (前10):')
for d, c in dates.most_common(10):
    print(f'  {d}: {c} 条')

# RoadCat 分布
roadcats = Counter(str(r.get('RoadCat', 'N/A')) for r in records)
print(f'\nRoadCat 分布:')
for rc, c in sorted(roadcats.items()):
    print(f'  {rc}: {c} 条')

# 非 7/8 的记录
non_78 = [r for r in records if str(r.get('HourOfDate')) not in ('7', '8')]
print(f'\n非 7/8 的记录: {len(non_78)} 条')
if non_78:
    print(f'  示例 HourOfDate: {list(set(str(r.get("HourOfDate")) for r in non_78))[:10]}')

# 样本
print(f'\n样本记录:')
print(json.dumps(records[0], indent=2))
