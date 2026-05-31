import logging

from celery import shared_task

from apps.saft.services.export import mark_saft_export_error, process_saft_export_job

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=900,
    retry_jitter=True,
    max_retries=3,
    queue="low_priority",
)
def generate_saft_export(self, job_id: str):
    try:
        process_saft_export_job(job_id=job_id)
    except Exception as exc:
        logger.exception("SAFT export failed for job %s", job_id)
        mark_saft_export_error(job_id=job_id, error_message=str(exc))
        raise exc
