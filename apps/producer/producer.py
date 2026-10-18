import json
import logging
import os
import random
import signal
import time
from datetime import datetime, timezone

from kafka import KafkaProducer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"
)
TOPIC = os.getenv("KAFKA_TOPIC", "bus.telemetry.raw")
INTERVAL = float(os.getenv("PUBLISH_INTERVAL", "2"))

running = True


def shutdown(signum, frame):
    global running
    logging.info("Shutdown requested")
    running = False


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)


def create_event(bus_id):
    return {
        "bus_id": bus_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latitude": round(random.uniform(59.90, 59.95), 6),
        "longitude": round(random.uniform(10.70, 10.80), 6),
        "speed_kmh": round(random.uniform(0, 80), 2),
    }


def main():
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS.split(","),
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
        retries=5,
    )

    buses = ["BUS-101", "BUS-102", "BUS-103"]

    try:
        while running:
            for bus_id in buses:
                if not running:
                    break

                event = create_event(bus_id)

                future = producer.send(
                    TOPIC,
                    key=bus_id,
                    value=event,
                )

                metadata = future.get(timeout=10)

                logging.info(
                    "Published bus=%s partition=%s offset=%s",
                    bus_id,
                    metadata.partition,
                    metadata.offset,
                )

            time.sleep(INTERVAL)
    finally:
        producer.flush()
        producer.close()


if __name__ == "__main__":
    main()
