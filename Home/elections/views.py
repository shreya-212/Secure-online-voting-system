from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from .models import Election, Candidate
from .serializers import ElectionSerializer, ElectionListSerializer, CandidateSerializer


class IsAdminOrOfficer(permissions.BasePermission):
    """Allow admin and election officers to manage elections."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and request.user.role in ('admin', 'officer')


class ElectionViewSet(viewsets.ModelViewSet):
    """CRUD for elections. Admin/Officer can create/edit, voters can view."""
    permission_classes = [IsAdminOrOfficer]
    queryset = Election.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return ElectionListSerializer
        return ElectionSerializer

    def get_queryset(self):
        qs = Election.objects.all()
        user = self.request.user

        # Filter by query params
        level = self.request.query_params.get('level')
        stat = self.request.query_params.get('status')
        state = self.request.query_params.get('state')

        if level:
            qs = qs.filter(level=level)
        if stat:
            qs = qs.filter(status=stat)
        if state:
            qs = qs.filter(state=state)

        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Return currently active elections."""
        now = timezone.now()
        elections = Election.objects.filter(
            start_time__lte=now, end_time__gte=now, status='active'
        )
        serializer = ElectionListSerializer(elections, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def eligible(self, request):
        """Return elections the current user is eligible for."""
        user = request.user
        now = timezone.now()
        elections = Election.objects.filter(
            start_time__lte=now, end_time__gte=now, status='active'
        )
        # Filter by user's constituency
        eligible = []
        for el in elections:
            if el.level == 'national':
                eligible.append(el)
            elif el.level == 'state' and el.state == user.state:
                eligible.append(el)
            elif el.level == 'village' and el.state == user.state and el.district == user.district and el.village == user.village:
                eligible.append(el)
        serializer = ElectionListSerializer(eligible, many=True)
        return Response(serializer.data)


class CandidateViewSet(viewsets.ModelViewSet):
    """CRUD for candidates. Admin/Officer can manage."""
    serializer_class = CandidateSerializer
    permission_classes = [IsAdminOrOfficer]

    def get_queryset(self):
        qs = Candidate.objects.all()
        election_id = self.request.query_params.get('election')
        if election_id:
            qs = qs.filter(election_id=election_id)
        return qs
