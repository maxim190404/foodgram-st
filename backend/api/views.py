from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from djoser.views import UserViewSet as DjoserUserViewSet
from users.models import Follow
from recipes.models import (Ingredient, Recipe, ShoppingCart, Favorite,
                            RecipeIngredient)
from .serializers import (
    IngredientSerializer, RecipeSerializer, FavoriteSerializer,
    ShoppingCartSerializer, FollowSerializer, CustomUserSerializer,
    CustomUserCreateSerializer, SetPasswordSerializer,
    UserWithRecipesSerializer, SetAvatarSerializer,
    RecipeCreateResponseSerializer, RecipeUpdateSerializer
)
from django.core.files.base import ContentFile
import base64
import uuid
from django.http import HttpResponse
from .pagination import StandardResultsSetPagination
from django.db.models import Count
from .filters import RecipeFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from .permissions import IsAuthorOrReadOnly

User = get_user_model()


class UserViewSet(DjoserUserViewSet):
    serializer_class = CustomUserSerializer
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'create']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return CustomUserCreateSerializer
        return CustomUserSerializer

    @action(detail=False, methods=['put', 'delete'],
            permission_classes=[IsAuthenticated], url_path='me/avatar')
    def avatar(self, request):
        user = request.user

        if request.method == 'PUT':
            if 'avatar' not in request.data:
                return Response(
                    {'error': 'Необходимо передать изображение в поле avatar'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            image_data = request.data['avatar']
            if (isinstance(image_data, str)
                    and image_data.startswith('data:image')):
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]
                mime_type = format.replace('data:', '')
                data = ContentFile(
                    base64.b64decode(imgstr),
                    name=f'{uuid.uuid4()}.{ext}'
                )
                user.avatar = data
                user.save()
                serializer = SetAvatarSerializer(
                    user, context={'mime_type': mime_type})
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(
                {'error': 'Некорректный формат изображения'},
                status=status.HTTP_400_BAD_REQUEST
            )
        elif request.method == 'DELETE':
            if not user.avatar:
                return Response(
                    {'error': 'Аватар не установлен'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.avatar.delete()
            user.avatar = None
            user.save()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated], url_path='subscribe')
    def subscribe(self, request, id=None):
        user = request.user
        author = get_object_or_404(User, id=id)
        if request.method == 'POST':
            if user == author:
                return Response(
                    {'errors': 'Нельзя подписаться на самого себя'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if Follow.objects.filter(user=user, author=author).exists():
                return Response(
                    {'errors': 'Вы уже подписаны на этого автора'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            follow = Follow.objects.create(user=user, author=author)
            serializer = FollowSerializer(
                follow,
                context={'request': request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        elif request.method == 'DELETE':
            if not Follow.objects.filter(user=user, author=author).exists():
                return Response(
                    {"detail": "Подписка не существует."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            follow = Follow.objects.get(user=user, author=author)
            follow.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False,
            methods=['post'],
            permission_classes=[IsAuthenticated])
    def set_password(self, request):
        serializer = SetPasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='subscriptions')
    def subscriptions(self, request):
        queryset = User.objects.filter(
            following__user=request.user
        ).annotate(
            recipes_count=Count('recipes')
        ).prefetch_related('recipes').order_by('id')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = UserWithRecipesSerializer(
                page,
                many=True,
                context={
                    'request': request,
                    'recipes_limit': request.query_params.get('recipes_limit')
                }
            )
            return self.get_paginated_response(serializer.data)

        serializer = UserWithRecipesSerializer(
            queryset,
            many=True,
            context={
                'request': request,
                'recipes_limit': request.query_params.get('recipes_limit')
            }
        )
        return Response(serializer.data)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        search_term = self.request.query_params.get('name', None)
        if search_term:
            queryset = queryset.filter(name__istartswith=search_term)
        return queryset


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    permission_classes = [IsAuthorOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = RecipeFilter

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated:
            return queryset
        return queryset

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return RecipeUpdateSerializer
        return RecipeSerializer

    def perform_create(self, serializer):
        if ('image' in serializer.validated_data
                and isinstance(serializer.validated_data['image'], str)):
            image_data = serializer.validated_data['image']
            if image_data.startswith('data:image'):
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]

                data = ContentFile(
                    base64.b64decode(imgstr),
                    name=f'{uuid.uuid4()}.{ext}'
                )
                serializer.validated_data['image'] = data

        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        if ('image' in serializer.validated_data
                and isinstance(serializer.validated_data['image'], str)):
            image_data = serializer.validated_data['image']
            if image_data.startswith('data:image'):
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]

                data = ContentFile(
                    base64.b64decode(imgstr),
                    name=f'{uuid.uuid4()}.{ext}'
                )
                serializer.validated_data['image'] = data

        serializer.save()

    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Аутентификация требуется для создания рецепта."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        response_serializer = RecipeCreateResponseSerializer(
            serializer.instance,
            context={'request': request}
        )
        return Response(response_serializer.data,
                        status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance,
                                         data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(RecipeCreateResponseSerializer(
            instance, context={'request': request}).data)

        response_serializer = RecipeCreateResponseSerializer(
            instance,
            context={'request': request}
        )
        return Response(response_serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = RecipeCreateResponseSerializer(
            instance, context={'request': request})
        return Response(serializer.data)

    @action(detail=True,
            methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def favorite(self, request, pk=None):
        recipe = get_object_or_404(Recipe, id=pk)

        if request.method == 'POST':
            if Favorite.objects.filter(user=request.user,
                                       recipe=recipe).exists():
                return Response(
                    {'errors': 'Рецепт уже в избранном'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            favorite = Favorite.objects.create(
                user=request.user, recipe=recipe)
            serializer = FavoriteSerializer(
                favorite,
                context={'request': request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == 'DELETE':
            favorite = Favorite.objects.filter(
                user=request.user, recipe=recipe).first()
            if not favorite:
                return Response(
                    {'errors': 'Рецепт не находится в избранном.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            favorite.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def shopping_cart(self, request, pk=None):
        recipe = get_object_or_404(Recipe, id=pk)

        if request.method == 'POST':
            if ShoppingCart.objects.filter(user=request.user,
                                           recipe=recipe).exists():
                return Response(
                    {'errors': 'Рецепт уже в списке покупок'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            cart_item = ShoppingCart.objects.create(
                user=request.user, recipe=recipe)
            serializer = ShoppingCartSerializer(
                cart_item, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == 'DELETE':
            cart_item = ShoppingCart.objects.filter(
                user=request.user, recipe=recipe).first()
            if not cart_item:
                return Response(
                    {'errors': 'Рецепт не находится в корзине покупок.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            cart_item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated])
    def download_shopping_cart(self, request):
        shopping_cart = ShoppingCart.objects.filter(user=request.user)
        if not shopping_cart.exists():
            return Response({'error': 'Корзина покупок пуста'},
                            status=status.HTTP_400_BAD_REQUEST)

        recipes = shopping_cart.values_list('recipe', flat=True)
        recipe_ingredients = RecipeIngredient.objects.filter(
            recipe__in=recipes)

        ingredients = recipe_ingredients.values(
            'ingredient__name', 'ingredient__measurement_unit'
        ).annotate(amount=models.Sum('amount'))

        content = "Список покупок:\n\n"
        for item in ingredients:
            content += (
                f"{item['ingredient__name']}"
                f"({item['ingredient__measurement_unit']}): "
                f"{item['amount']}\n"
            )

        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"')
        return response

    @action(detail=True, methods=["get"], url_path="get-link")
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        base_url = request.build_absolute_uri('/')[:-1]
        return Response(
            {"short-link": f"{base_url}/recipes/{recipe.id}"},
            status=status.HTTP_200_OK,
        )
