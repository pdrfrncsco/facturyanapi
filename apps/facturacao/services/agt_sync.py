from django.db import transaction
from django.utils import timezone

from apps.auditoria.services.audit_logs import create_audit_log
from apps.common.task_dispatch import dispatch_task
from apps.facturacao.integrations.agt.client import AgtClient
from apps.facturacao.models import AgtSyncLog, Invoice


def queue_agt_sync(*, invoice: Invoice) -> AgtSyncLog:
    client = AgtClient()
    payload = client.build_invoice_payload(invoice=invoice)
    sync_log = AgtSyncLog.objects.create(
        empresa=invoice.empresa,
        invoice=invoice,
        status=AgtSyncLog.Status.PENDING,
        request_payload=payload,
        response_code="PENDING",
    )
    enqueue_agt_sync_processing(sync_log=sync_log)
    return sync_log


def queue_agt_cancellation(*, invoice: Invoice) -> AgtSyncLog:
    client = AgtClient()
    payload = client.build_cancellation_payload(invoice=invoice)
    sync_log = AgtSyncLog.objects.create(
        empresa=invoice.empresa,
        invoice=invoice,
        status=AgtSyncLog.Status.PENDING,
        request_payload=payload,
        response_code="CANCEL_PENDING",
    )
    enqueue_agt_sync_processing(sync_log=sync_log)
    return sync_log


def enqueue_agt_sync_processing(*, sync_log: AgtSyncLog) -> None:
    from apps.facturacao.tasks.agt_sync import process_agt_sync_log

    dispatch_task(process_agt_sync_log, str(sync_log.id))


def trigger_agt_sync(*, invoice: Invoice) -> AgtSyncLog:
    sync_log = (
        invoice.agt_sync_logs.filter(status__in=[AgtSyncLog.Status.PENDING, AgtSyncLog.Status.ERROR])
        .order_by("-created_at")
        .first()
    )
    if sync_log is None:
        if invoice.status == Invoice.Status.CANCELLED:
            return queue_agt_cancellation(invoice=invoice)
        return queue_agt_sync(invoice=invoice)

    if sync_log.status == AgtSyncLog.Status.ERROR:
        sync_log.status = AgtSyncLog.Status.PENDING
        sync_log.error_message = ""
        sync_log.save(update_fields=["status", "error_message", "updated_at"])
    enqueue_agt_sync_processing(sync_log=sync_log)
    return sync_log


def enqueue_invoice_pdf(*, invoice: Invoice) -> None:
    from apps.facturacao.services.pdf_generation import create_or_reset_invoice_document
    from apps.facturacao.tasks.pdf_generation import generate_invoice_pdf

    document = create_or_reset_invoice_document(invoice=invoice)
    dispatch_task(generate_invoice_pdf, str(document.id))


class AgtTerminalError(RuntimeError):
    """Erro fatal que não deve ser re-tentado automaticamente."""
    pass


class AgtTransientError(RuntimeError):
    """Erro temporário que pode ser re-tentado."""
    pass


@transaction.atomic
def process_agt_sync_log(*, sync_log_id: str) -> AgtSyncLog:
    sync_log = (
        AgtSyncLog.objects.select_for_update()
        .select_related("invoice", "invoice__empresa", "empresa")
        .get(pk=sync_log_id)
    )
    invoice = sync_log.invoice
    
    # Se já teve sucesso ou está a aguardar (será tratado pelo polling), ignorar
    if sync_log.status in {AgtSyncLog.Status.SUCCESS, AgtSyncLog.Status.WAITING}:
        return sync_log

    sync_log.attempt_count += 1
    client = AgtClient()
    result = client.submit(payload=sync_log.request_payload)

    if result.success:
        # AGT devolve um requestID para modelos assíncronos
        sync_log.request_id = result.request_id
        sync_log.status = AgtSyncLog.Status.WAITING
        sync_log.response_code = result.response_code
        sync_log.response_payload = result.response_payload
        sync_log.error_message = ""
        sync_log.save(
            update_fields=["request_id", "status", "response_code", "response_payload", "error_message", "attempt_count", "updated_at"]
        )
        
        # Enfileirar polling
        from apps.facturacao.tasks.agt_sync import poll_agt_status
        dispatch_task(poll_agt_status, str(sync_log.id))
        
        return sync_log

    # Falha na submissão
    sync_log.status = AgtSyncLog.Status.ERROR
    sync_log.response_code = result.response_code
    sync_log.response_payload = result.response_payload
    sync_log.error_message = result.error_message
    sync_log.save(
        update_fields=["status", "response_code", "response_payload", "error_message", "attempt_count", "updated_at"]
    )
    
    if invoice.status not in {Invoice.Status.CANCELLED, Invoice.Status.DRAFT}:
        invoice.status = Invoice.Status.AGT_ERROR
        invoice.agt_response_code = result.response_code
        invoice.save(update_fields=["status", "agt_response_code", "updated_at"])

    create_audit_log(
        empresa=sync_log.empresa,
        user=None,
        action="AGT_SYNC_FAILURE",
        details=f"Falha na sincronização AGT para {invoice.invoice_no} (Tentativa {sync_log.attempt_count}). Erro: {result.error_message}",
        entity_type="invoice",
        entity_id=str(invoice.id),
    )
    
    if result.is_transient:
        raise AgtTransientError(result.error_message or "Falha temporária na sincronização AGT.")
    
    raise AgtTerminalError(result.error_message or "Falha terminal na sincronização AGT.")


@transaction.atomic
def poll_agt_status(*, sync_log_id: str) -> AgtSyncLog:
    """
    Consulta o estado de um pedido assíncrono na AGT.
    """
    sync_log = (
        AgtSyncLog.objects.select_for_update()
        .select_related("invoice", "invoice__empresa", "empresa")
        .get(pk=sync_log_id)
    )
    
    if sync_log.status != AgtSyncLog.Status.WAITING or not sync_log.request_id:
        return sync_log

    client = AgtClient()
    result = client.get_status(empresa=sync_log.empresa, request_id=sync_log.request_id)

    if result.success:
        # Em mock retorna sucesso logo. Em prod validamos o payload.
        sync_log.status = AgtSyncLog.Status.SUCCESS
        sync_log.response_code = result.response_code
        sync_log.response_payload = result.response_payload
        sync_log.save(update_fields=["status", "response_code", "response_payload", "updated_at"])
        
        invoice = sync_log.invoice
        action = sync_log.request_payload.get("action", "issue")
        invoice.agt_sync_date = timezone.now()
        invoice.agt_response_code = result.response_code
        
        if action == "cancel":
            invoice.save(update_fields=["agt_sync_date", "agt_response_code", "updated_at"])
        elif invoice.status in {Invoice.Status.ISSUED, Invoice.Status.AGT_ERROR}:
            invoice.status = Invoice.Status.AGT_SYNCED
            invoice.save(update_fields=["status", "agt_sync_date", "agt_response_code", "updated_at"])
        
        create_audit_log(
            empresa=sync_log.empresa,
            user=None,
            action="AGT_STATUS_CONFIRMED",
            details=f"Validação AGT confirmada para {invoice.invoice_no}. Código: {result.response_code}",
            entity_type="invoice",
            entity_id=str(invoice.id),
        )
    else:
        if result.is_transient:
            raise AgtTransientError("AGT ainda a processar ou indisponível temporariamente.")
        
        # Erro terminal na validação (rejeitada pela AGT)
        sync_log.status = AgtSyncLog.Status.ERROR
        sync_log.error_message = result.error_message
        sync_log.save(update_fields=["status", "error_message", "updated_at"])
        
        invoice = sync_log.invoice
        invoice.status = Invoice.Status.AGT_ERROR
        invoice.save(update_fields=["status", "updated_at"])
        
        raise AgtTerminalError(f"Documento rejeitado pela AGT: {result.error_message}")

    return sync_log
