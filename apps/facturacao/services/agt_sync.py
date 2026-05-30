from apps.facturacao.integrations.agt.client import AgtClient
from apps.facturacao.models import AgtSyncLog, Invoice


def queue_agt_sync(*, invoice: Invoice) -> AgtSyncLog:
    client = AgtClient()
    payload = client.build_invoice_payload(invoice=invoice)
    return AgtSyncLog.objects.create(
        empresa=invoice.empresa,
        invoice=invoice,
        status=AgtSyncLog.Status.PENDING,
        request_payload=payload,
        response_code="PENDING",
    )


def queue_agt_cancellation(*, invoice: Invoice) -> AgtSyncLog:
    client = AgtClient()
    payload = client.build_cancellation_payload(invoice=invoice)
    return AgtSyncLog.objects.create(
        empresa=invoice.empresa,
        invoice=invoice,
        status=AgtSyncLog.Status.PENDING,
        request_payload=payload,
        response_code="CANCEL_PENDING",
    )
