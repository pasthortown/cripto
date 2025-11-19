from pymongo import MongoClient
from datetime import datetime, timezone

client = MongoClient('mongodb://admin:SecurePass123!@mongodb:27017/')
db = client['binance_data']
collection = db['predictions_bnbusdt']

now = datetime.now(timezone.utc)
today_17 = now.replace(hour=17, minute=0, second=0, microsecond=0)
timestamp_17 = int(today_17.timestamp() * 1000)

print(f'Timestamp 17:00 hoy (UTC): {timestamp_17} ({today_17.isoformat()})')
print(f'Hora actual: {now.isoformat()}')

count = collection.count_documents({'open_time': {'$gte': timestamp_17}})
print(f'Total predicciones con open_time >= 17:00: {count}')

print('\nPrimeras 10 predicciones desde las 17:00:')
for pred in collection.find({'open_time': {'$gte': timestamp_17}}).sort('open_time', 1).limit(10):
    ot = datetime.fromtimestamp(pred['open_time'] / 1000, tz=timezone.utc)
    ct = datetime.fromtimestamp(pred['close_time'] / 1000, tz=timezone.utc)
    print(f'  open_time: {ot.isoformat()} | close_time: {ct.isoformat()} | horizon: {pred["horizon_minutes"]}min')
