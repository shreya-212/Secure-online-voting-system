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

        if user.is_authenticated and user.role == 'voter':
            from django.db.models import Q
            q_national = Q(level='national')
            q_state = Q(level='state', state__iexact=user.state)
            q_village = Q(level='village', state__iexact=user.state, district__iexact=user.district, village__iexact=user.village)
            qs = qs.filter(q_national | q_state | q_village).filter(approval_status='approved')

        # Filter by query params
        level = self.request.query_params.get('level')
        stat = self.request.query_params.get('status')
        state = self.request.query_params.get('state')

        if level:
            qs = qs.filter(level=level)
        if stat:
            qs = qs.filter(status=stat)
        if state:
            qs = qs.filter(state__iexact=state)

        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        user = self.request.user
        level = serializer.validated_data.get('level')
        village = serializer.validated_data.get('village')
        state = serializer.validated_data.get('state')
        district = serializer.validated_data.get('district')
        
        from rest_framework.exceptions import ValidationError
        
        # Enforce rule: Only one active/upcoming election permitted
        existing = Election.objects.filter(level=level, status__in=['active', 'upcoming'])
        
        if level == 'village' and village:
            existing = existing.filter(village=village, district=district, state=state)
        elif level == 'state' and state:
            existing = existing.filter(state=state)
            
        if existing.exists():
            raise ValidationError({'detail': 'An active or upcoming election already exists. More than one election is not permitted.'})

        # Set approval status based on who creates it. State Admins (officers) don't need approval.
        approval_status = 'approved' if self.request.user.role == 'officer' else 'pending'
        serializer.save(created_by=self.request.user, approval_status=approval_status)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if request.user.role != 'officer':
            return Response({'detail': 'Only State Administrative can approve elections.'}, status=status.HTTP_403_FORBIDDEN)
        election = self.get_object()
        election.approval_status = 'approved'
        election.save()
        return Response({'status': 'approved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if request.user.role != 'officer':
            return Response({'detail': 'Only State Administrative can reject elections.'}, status=status.HTTP_403_FORBIDDEN)
        election = self.get_object()
        election.approval_status = 'rejected'
        election.status = 'cancelled'
        election.save()
        return Response({'status': 'rejected'})

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Return currently active elections."""
        now = timezone.now()
        elections = self.get_queryset().filter(
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
            start_time__lte=now, end_time__gte=now, status='active', approval_status='approved'
        )
        # Helper for strict alignment
        def normalize(loc):
            return (loc or '').lower().replace(' ', '')

        # Filter by user's constituency
        eligible = []
        for el in elections:
            if el.level == 'national':
                eligible.append(el)
            elif el.level == 'state' and normalize(el.state) == normalize(user.state):
                eligible.append(el)
            elif el.level == 'village':
                state_match = normalize(el.state) == normalize(user.state)
                dist_match = normalize(el.district) == normalize(user.district)
                vill_match = normalize(el.village) == normalize(user.village)
                if state_match and dist_match and vill_match:
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
