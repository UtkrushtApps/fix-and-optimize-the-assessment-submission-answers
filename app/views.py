from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets

from .models import Submission
from .serializers import SubmissionSerializer


class SubmissionViewSet(viewsets.ModelViewSet):
    serializer_class = SubmissionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        queryset = Submission.objects.select_related('candidate', 'assessment')

        if self.request.user.is_staff:
            return queryset

        return queryset.filter(candidate=self.request.user)

    def perform_create(self, serializer):
        serializer.save(candidate=self.request.user)
