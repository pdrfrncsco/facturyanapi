from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import TenantRolePermission
from apps.saft.serializers.export import SaftExportSerializer
from apps.saft.services.export import request_saft_export


class SaftExportView(APIView):
    permission_classes = [TenantRolePermission]
    write_roles = {
        "Admin",
        "Financial_Director",
        "Auditor",
    }

    def post(self, request):
        serializer = SaftExportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = request_saft_export(
            empresa=request.empresa,
            user=request.user,
            year=serializer.validated_data["year"],
            month=serializer.validated_data["month"],
            request=request,
        )
        return Response(result, status=status.HTTP_202_ACCEPTED)
