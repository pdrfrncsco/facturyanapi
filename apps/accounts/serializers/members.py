from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.empresas.models import EmpresaMembership

User = get_user_model()


class TenantMemberSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    userId = serializers.UUIDField(source="user.id", read_only=True)
    name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    membershipRole = serializers.CharField(source="role", read_only=True)
    isActive = serializers.BooleanField(source="user.is_active", read_only=True)
    isDefault = serializers.BooleanField(source="is_default", read_only=True)
    status = serializers.SerializerMethodField()
    isSelf = serializers.SerializerMethodField()
    joinedAt = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = EmpresaMembership
        fields = [
            "id",
            "userId",
            "name",
            "email",
            "role",
            "membershipRole",
            "isActive",
            "isDefault",
            "status",
            "isSelf",
            "joinedAt",
        ]

    def get_status(self, obj: EmpresaMembership) -> str:
        return "Active" if obj.user.is_active else "Suspended"

    def get_isSelf(self, obj: EmpresaMembership) -> bool:
        request = self.context.get("request")
        return bool(request and getattr(request, "user", None) and obj.user_id == request.user.id)


class TenantMemberUpdateSerializer(serializers.Serializer):
    isActive = serializers.BooleanField(required=False)
    role = serializers.ChoiceField(choices=User.Role.choices, required=False)

    def validate(self, attrs):
        request = self.context["request"]
        membership: EmpresaMembership = self.instance

        if "isActive" not in attrs and "role" not in attrs:
            raise serializers.ValidationError("Nenhuma alteração foi enviada.")

        if membership.user_id == request.user.id and attrs.get("isActive") is False:
            raise serializers.ValidationError({"isActive": "Não é possível desactivar o próprio utilizador."})

        return attrs

    def update(self, instance: EmpresaMembership, validated_data):
        user = instance.user
        updated_fields = []

        if "isActive" in validated_data:
            user.is_active = validated_data["isActive"]
            updated_fields.append("is_active")

        if "role" in validated_data:
            user.role = validated_data["role"]
            updated_fields.append("role")

        if updated_fields:
            user.save(update_fields=updated_fields)

        return instance
