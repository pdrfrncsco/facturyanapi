from rest_framework import serializers

from apps.saft.models import SaftExportJob


class SaftExportJobSerializer(serializers.ModelSerializer):
    jobId = serializers.UUIDField(source="id", read_only=True)
    downloadUrl = serializers.SerializerMethodField()

    class Meta:
        model = SaftExportJob
        fields = ["jobId", "year", "month", "status", "filename", "downloadUrl", "errorMessage", "createdAt"]

    errorMessage = serializers.CharField(source="error_message", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)

    def get_downloadUrl(self, obj) -> str | None:
        if obj.status != SaftExportJob.Status.READY or not obj.file:
            return None
        request = self.context.get("request")
        if request is None:
            return None
        return request.build_absolute_uri(f"/api/v1/saft/export/{obj.id}/")
