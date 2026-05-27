from django.contrib.auth.models import User
from django.db import IntegrityError
from rest_framework import serializers

from .models import Assessment, Submission


class AssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assessment
        fields = ['id', 'title', 'max_score']


class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class SubmissionSerializer(serializers.ModelSerializer):
    candidate = CandidateSerializer(read_only=True)
    assessment = AssessmentSerializer(read_only=True)
    assessment_id = serializers.PrimaryKeyRelatedField(
        queryset=Assessment.objects.all(),
        source='assessment',
        write_only=True
    )

    class Meta:
        model = Submission
        fields = [
            'id',
            'candidate',
            'assessment',
            'assessment_id',
            'status',
            'score',
            'submitted_at',
        ]
        read_only_fields = ['id', 'candidate', 'status', 'score', 'submitted_at']

    def validate(self, attrs):
        request = self.context.get('request')
        assessment = attrs.get('assessment')

        if (
            request is not None
            and request.method == 'POST'
            and request.user.is_authenticated
            and assessment is not None
            and Submission.objects.filter(
                candidate=request.user,
                assessment=assessment,
            ).exists()
        ):
            raise serializers.ValidationError({
                'assessment_id': 'You have already submitted for this assessment.'
            })

        return attrs

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError({
                'assessment_id': 'You have already submitted for this assessment.'
            })
