from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Magazine
from .serializers import MagazineSerializer


ADMIN_ROLES = {"admin", "super_admin"}


def get_role_name(user):
    role = getattr(user, "role", None)

    if role is None:
        return None

    return getattr(role, "name", str(role))


def is_admin_user(user):
    if not user or not user.is_authenticated:
        return False

    return get_role_name(user) in ADMIN_ROLES


def is_active_subscriber(user):
    if not user or not user.is_authenticated:
        return False

    role_name = get_role_name(user)

    return (
        role_name == "subscriber"
        and getattr(user, "status", None) == "active"
    )


class MagazineListCreateView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def get(self, request):
        if is_admin_user(request.user):
            magazines = Magazine.objects.all()
        elif is_active_subscriber(request.user):
            magazines = Magazine.objects.filter(
                status=Magazine.PUBLISHED
            )
        else:
            return Response(
                {"detail": "You do not have permission to view magazines."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = MagazineSerializer(
            magazines,
            many=True,
            context={"request": request},
        )

        return Response(serializer.data)

    def post(self, request):
        if not is_admin_user(request.user):
            return Response(
                {"detail": "Only administrators can create magazines."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = MagazineSerializer(
            data=request.data,
            context={"request": request},
        )

        if serializer.is_valid():
            magazine = serializer.save()

            return Response(
                MagazineSerializer(
                    magazine,
                    context={"request": request},
                ).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


class MagazineDetailView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            magazine = Magazine.objects.get(pk=pk)
        except Magazine.DoesNotExist:
            return Response(
                {"detail": "Magazine not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if is_admin_user(request.user):
            pass
        elif is_active_subscriber(request.user):
            if magazine.status != Magazine.PUBLISHED:
                return Response(
                    {"detail": "Magazine not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            return Response(
                {"detail": "You do not have permission to view this magazine."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = MagazineSerializer(
            magazine,
            context={"request": request},
        )

        return Response(serializer.data)

    def patch(self, request, pk):
        if not is_admin_user(request.user):
            return Response(
                {"detail": "Only administrators can update magazines."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            magazine = Magazine.objects.get(pk=pk)
        except Magazine.DoesNotExist:
            return Response(
                {"detail": "Magazine not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = MagazineSerializer(
            magazine,
            data=request.data,
            partial=True,
            context={"request": request},
        )

        if serializer.is_valid():
            magazine = serializer.save()

            return Response(
                MagazineSerializer(
                    magazine,
                    context={"request": request},
                ).data
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, pk):
        if not is_admin_user(request.user):
            return Response(
                {"detail": "Only administrators can delete magazines."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            magazine = Magazine.objects.get(pk=pk)
        except Magazine.DoesNotExist:
            return Response(
                {"detail": "Magazine not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        magazine.delete()

        return Response(
            {"detail": "Magazine deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )