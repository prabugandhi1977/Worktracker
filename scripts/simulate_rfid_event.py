"""
Publishes a fake RFID scan to the MQTT broker so you can see an event flow
through the pipeline without real hardware. Requires the seed data (scripts/seed.py).

Usage:
  python scripts/simulate_rfid_event.py --reader READER-GATE-01 --card CARD-DEMO-001
  python scripts/simulate_rfid_event.py --reader READER-PRJ-001 --card CARD-DEMO-001
"""

import argparse
import json
import uuid
from datetime import datetime, timezone

import paho.mqtt.publish as publish

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="localhost")
parser.add_argument("--port", type=int, default=1883)
parser.add_argument("--site", default="site1")
parser.add_argument("--gateway", default="GW-01")
parser.add_argument("--reader", required=True)
parser.add_argument("--card", required=True)
args = parser.parse_args()

payload = {
    "event_id": str(uuid.uuid4()),
    "rfid_uid": args.card,
    "reader_id": args.reader,
    "gateway_id": args.gateway,
    "timestamp": datetime.now(timezone.utc).isoformat(),
}

topic = f"company/{args.site}/{args.gateway}/rfid/events"
publish.single(topic, payload=json.dumps(payload), hostname=args.host, port=args.port, qos=1)
print(f"Published to {topic}:")
print(json.dumps(payload, indent=2))
