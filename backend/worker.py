from __future__ import annotations

import os
import time

import pika

from mongo_store import init_mongo, get_upload_job, set_upload_job_status
from services.pipeline import process_log_text

QUEUE_NAME = "debugiq_uploads"


def _consume_forever() -> None:
    rabbit_url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
    params = pika.URLParameters(rabbit_url)

    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.basic_qos(prefetch_count=1)

    def _handle_message(ch, method, properties, body) -> None:
        job_id_raw = body.decode("utf-8", errors="ignore").strip()
        try:
            job_id = int(job_id_raw)
        except ValueError:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        job = get_upload_job(job_id)
        if not job:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        set_upload_job_status(job_id, "processing")
        raw_logs = job["raw_logs_text"]
        filename = job["filename"]
        user_id = job.get("user_id")

        try:
            result = process_log_text(raw_logs, filename, user_id=user_id)
            run_id = int(result["run_id"])

            set_upload_job_status(job_id, "completed", run_id=run_id)
        except Exception as exc:  # pragma: no cover
            set_upload_job_status(job_id, "failed", error=str(exc))

        # Ack regardless: we mark failures in DB to avoid poison-pill loops.
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=_handle_message, auto_ack=False)
    print(f"[DebugIQ worker] Consuming from '{QUEUE_NAME}' ...")
    channel.start_consuming()


if __name__ == "__main__":
    init_mongo()
    while True:
        try:
            _consume_forever()
        except Exception as exc:  # pragma: no cover
            print(f"[DebugIQ worker] connection error: {exc}; retrying...")
            time.sleep(5)

