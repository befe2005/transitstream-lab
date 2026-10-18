import json
import logging
import os
import signal

from kafka import KafkaConsumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"
)
TOPIC = os.getenv("KAFKA_TOPIC", "bus.telemetry.raw")
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "transitstream-processors")

running = True


def shutdown(signum, frame):
    global running
    logging.info("Shutdown requested")
    running = False


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)


def main():
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS.split(","),
        group_id=GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )

    try:
        while running:
            batches = consumer.poll(timeout_ms=1000)

            for partition, messages in batches.items():
                for message in messages:
                    event = message.value

                    logging.info(
                        "Processed bus=%s speed=%s "
                        "partition=%s offset=%s",
                        event.get("bus_id"),
                        event.get("speed_kmh"),
                        message.partition,
                        message.offset,
                    )

                # Commit only after the batch is processed.
                consumer.commit()
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
