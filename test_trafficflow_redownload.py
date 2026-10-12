"""重新下载 TrafficFlow，检查 HourOfDate 分布和数据完整性"""
import requests
import json
import os
from datetime import datetime
from collections import Counter

API_KEY = 'zv7bb9ZNTVKLgh4cMALjMQ=='
headers = {'AccountKey': API_KEY, 'Accept': 'application/json'}
BASE = 'https://datamall2.mytransport.sg/ltaodataservice'

print(f'[{datetime.now()}] Step 1: 调用 TrafficFlow API 获取 S3 链接...')
r = requests.get(f'{BASE}/TrafficFlow', headers=headers, timeout=30)
print(f'  Status: {r.status_code}')

if r.status_code != 200:
    print(f'  API 失败: {r.text[:300]}')
    exit(1)

link_data = r.json()
print(f'  返回结构: {list(link_data.keys())}')

values = link_data.get('value', [])
if not values or 'Link' not in values[0]:
    print(f'  未找到 S3 链接。返回内容: {json.dumps(link_data, indent=2)[:500]}')
    exit(1)

s3_url = values[0]['Link']
print(f'  S3 链接: {s3_url[:80]}...')

print(f'\n[{datetime.now()}] Step 2: 从 S3 下载实际数据...')
r2 = requests.get(s3_url, timeout=300)
print(f'  Status: {r2.status_code}, Size: {len(r2.content)/1024/1024:.1f} MB')

if r2.status_code != 200:
    print(f'  S3 下载失败: {r2.text[:300]}')
    exit(1)

# 保存
save_path = 'TrafficFlow_redownload_test.json'
with open(save_path, 'wb') as f:
    f.write(r2.content)
print(f'  已保存: {save_path}')

print(f'\n[{datetime.now()}] Step 3: 解析数据质量...')
with open(save_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

records = data.get('value', [])
print(f'  总记录数: {len(records)}')

if not records:
    print('  无记录！')
    exit(1)

# HourOfDate 分布
hours = Counter(str(r.get('HourOfDate', 'N/A')) for r in records)
print(f'\n  HourOfDate 分布:')
for h in sorted(hours.keys(), key=lambda x: (x != 'N/A', x)):
    print(f'    HourOfDate={h}: {hours[h]} 条')

# Date 分布
dates = Counter(str(r.get('Date', 'N/A')) for r in records)
print(f'\n  Date 分布 (前10):')
for d, c in dates.most_common(10):
    print(f'    {d}: {c} 条')

# RoadCat 分布
roadcats = Counter(str(r.get('RoadCat', 'N/A')) for r in records)
print(f'\n  RoadCat 分布:')
for rc, c in sorted(roadcats.items()):
    print(f'    {rc}: {c} 条')

# 检查是否有非 7/8 的小时
non_78 = [r for r in records if str(r.get('HourOfDate')) not in ('7', '8')]
print(f'\n  非 7/8 的记录: {len(non_78)} 条')
if non_78:
    print(f'    示例 HourOfDate: {list(set(str(r.get("HourOfDate")) for r in non_78))[:10]}')

# 样本记录
print(f'\n  样本记录:')
print(json.dumps(records[0], indent=2))
