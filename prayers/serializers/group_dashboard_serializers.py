from rest_framework import serializers


class GroupSummarySerializer(serializers.Serializer):
    """Read-only group metadata for dashboard."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    privacy_level = serializers.CharField()
    member_count = serializers.IntegerField()
    created_by = serializers.CharField()
    invite_code = serializers.CharField(allow_null=True)


class CurrentUserGroupSerializer(serializers.Serializer):
    """Current user's membership info in group."""
    role = serializers.CharField()
    joined_at = serializers.DateTimeField(allow_null=True)
    current_streak = serializers.IntegerField()
    rank = serializers.IntegerField(allow_null=True)


class LeaderboardEntrySerializer(serializers.Serializer):
    """Leaderboard entry for dashboard."""
    username = serializers.CharField()
    streak = serializers.IntegerField()
    rank = serializers.IntegerField()


class ActivitySerializer(serializers.Serializer):
    """Activity feed item for dashboard."""
    type = serializers.CharField()
    username = serializers.CharField()
    created_at = serializers.DateTimeField(allow_null=True)
    message = serializers.CharField(allow_null=True, required=False, allow_blank=True)


class TodayCompletionSerializer(serializers.Serializer):
    """Today's prayer completion stats."""
    fajr = serializers.IntegerField()
    dhuhr = serializers.IntegerField()
    asr = serializers.IntegerField()
    maghrib = serializers.IntegerField()
    isha = serializers.IntegerField()


class DashboardSerializer(serializers.Serializer):
    """Complete dashboard payload."""
    group = GroupSummarySerializer()
    current_user = CurrentUserGroupSerializer(allow_null=True)
    stats = serializers.DictField()
    top_streaks = LeaderboardEntrySerializer(many=True)
    recent_activity = ActivitySerializer(many=True)
    today_completion = TodayCompletionSerializer()
