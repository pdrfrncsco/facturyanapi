import logging

from celery import shared_task
from django.db import transaction

from apps.facturacao.services.agt_sync import (
    AgtTransientError,
    process_agt_sync_log as run_agt_sync,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(AgtTransientError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=10,
    queue="high_priority",
)
def process_agt_sync_log(self, sync_log_id: str):
    try:
        # A transação atómica já está no serviço
        run_agt_sync(sync_log_id=sync_log_id)
    except AgtTransientError as exc:
        logger.warning("AGT sync transient failure for log %s (attempt %s). Retrying...", sync_log_id, self.request.retries + 1)
        raise exc
    except Exception as exc:
        logger.error("AGT sync terminal failure or unexpected error for log %s: %s", sync_log_id, str(exc))
        # Não relançamos Exception genérica para evitar retentativas infinitas se configurado no autoretry_for
        # Mas como autoretry_for é específico para AgtTransientError, Exception genérica apenas falha o task.
        raise exc

