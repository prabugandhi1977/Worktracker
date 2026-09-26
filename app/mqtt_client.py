"""
IoT gateway integration (PRD section 12): subscribes to
`company/{site_id}/{gateway_id}/rfid/events` and feeds every message into the
event-processing service. Runs a background paho-mqtt network loop inside the
FastAPI process so a single container is enough to deploy the MVP.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import paho.mqtt.client as mqtt

from app.config import settings
from app.database import SessionLocal
from app.services.event_processor import process_rfid_event

logger = logging.getLogger("worktrack.mqtt")

REQUIRED_FIELDS = {"event_id", "rfid_uid", "reader_id", "gateway_id", "timestamp"}

_client: Optional[mqtt.Client] = None


def _on_connect(client: mqtt.Client, userdata, flags, rc) -> None:
    if rc == 0:
        logger.info("Connected to MQTT broker %s:%s", settings.MQTT_HOST, settings.MQTT_PORT)
        client.subscribe(settings.MQTT_TOPIC, qos=1)
    else:
        logger.error("MQTT connection failed with reason code %s", rc)


def _on_disconnect(client: mqtt.Client, userdata, rc) -> None:
    logger.warning("Disconnected from MQTT broker (rc=%s); paho will auto-reconnect", rc)


def _on_message(client: mqtt.Client, userdata, msg) -> None:
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("Discarding malformed MQTT payload on topic %s", msg.topic)
        return

    if not REQUIRED_FIELDS.issubset(payload):
        logger.warning("Discarding MQTT payload missing required fields: %s", payload)
        return

    try:
        event_timestamp = datetime.fromisoformat(str(payload["timestamp"]))
    except ValueError:
        logger.warning("Discarding MQTT payload with unparsable timestamp: %s", payload)
        return
    if event_timestamp.tzinfo is None:
        event_timestamp = event_timestamp.replace(tzinfo=timezone.utc)

    db = SessionLocal()
    try:
        process_rfid_event(
            db,
            event_uid=str(payload["event_id"]),
            card_uid=str(payload["rfid_uid"]),
            reader_code=str(payload["reader_id"]),
            gateway_code=str(payload["gateway_id"]),
            event_timestamp=event_timestamp,
            raw_payload=payload,
        )
    except Exception:
        db.rollback()
        logger.exception("Failed to process RFID event %s", payload.get("event_id"))
    finally:
        db.close()


def start_mqtt_listener() -> None:
    global _client
    if _client is not None:
        return

    client = mqtt.Client(client_id="worktrack-backend")
    if settings.MQTT_USERNAME:
        client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message = _on_message

    try:
        client.connect_async(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=60)
        client.loop_start()
        _client = client
    except Exception:
        logger.exception("Could not start MQTT listener; RFID events will only arrive via /events/rfid")


def stop_mqtt_listener() -> None:
    global _client
    if _client is not None:
        _client.loop_stop()
        _client.disconnect()
        _client = None
