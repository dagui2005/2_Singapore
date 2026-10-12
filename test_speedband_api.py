import requests
import json
from datetime import datetime

API_KEY = 'zv7bb9ZNTVKLgh4cMALjMQ=='
headers = {'AccountKey': API_KEY, 'Accept': 'application/json'}
url = 'https://datamall2.mytransport.sg/ltaodataservice/v4/TrafficSpeedBands'

print(f'[{datetime.now()}] Testing SpeedBand API...')
r = requests.get(url, headers=headers, timeout=30)
print(f'Status: {r.status_code}')
if r.status_code == 200:
    data = r.json()
    records = data.get('value', [])
    print(f'Total records in first page: {len(records)}')
    if records:
        print(f'Sample: {json.dumps(records[0], indent=2)[:500]}')
    print('API OK!')
else:
    print(f'Error: {r.text[:200]}')
