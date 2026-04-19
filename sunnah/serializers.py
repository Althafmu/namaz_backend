from rest_framework import serializers

from sunnah.models import SunnahLog


class SunnahLogWriteSerializer(serializers.Serializer):
    prayer_type = serializers.ChoiceField(choices=[value for value, _ in SunnahLog.PRAYER_TYPE_CHOICES])
    completed = serializers.BooleanField(required=False, default=True)
    date = serializers.DateField(required=False)


class SunnahLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SunnahLog
        fields = ('id', 'date', 'prayer_type', 'completed', 'created_at', 'updated_at')
        read_only_fields = fields
