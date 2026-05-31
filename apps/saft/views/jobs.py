from django.http import FileResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import TenantRolePermission
from apps.saft.models import SaftExportJob
from apps.saft.serializers.jobs import SaftExportJobSerializer


class SaftExportJobView(APIView):
    permission_classes = [TenantRolePermission]
    read_roles = {
        "Admin",
        "Financial_Director",
        "Auditor",
    }

    def get(self, request, job_id):
        job = SaftExportJob.objects.filter(pk=job_id, empresa=request.empresa).first()
        if job is None:
            return Response({"detail": "Exportação não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        if job.status == SaftExportJob.Status.READY and job.file:
            return FileResponse(job.file.open("rb"), as_attachment=True, filename=job.filename)
        return Response(SaftExportJobSerializer(job, context={"request": request}).data)
