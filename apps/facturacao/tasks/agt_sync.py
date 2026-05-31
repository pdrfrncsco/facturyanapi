import logging

from celery import shared_task
from django.db import transaction

from apps.facturacao.services.agt_sync import process_agt_sync_log as run_agt_sync

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
    queue="high_priority",
)
def process_agt_sync_log(self, sync_log_id: str):
    try:
        with transaction.atomic():
            run_agt_sync(sync_log_id=sync_log_id)
    except Exception as exc:
        logger.exception("AGT sync failed for log %s (attempt %s)", sync_log_id, self.request.retries + 1)
        raise exc
