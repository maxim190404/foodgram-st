from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from djoser.views import UserViewSet as DjoserUserViewSet
from recipes.models import (Ingredient, Recipe, ShoppingCart, Favorite,
                            RecipeIngredient)
from .serializers import (
    IngredientSerializer, RecipeSerializer, FavoriteSerializer,
    ShoppingCartSerializer, FollowSerializer, CustomUserSerializer,
    CustomUserCreateSerializer, SetPasswordSerializer,
    UserWithRecipesSerializer, SetAvatarSerializer,
    RecipeCreateUpdateSerializer
)
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
            serializer = SetAvatarSerializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            user.avatar = serializer.validated_data['avatar']
            user.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
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
            serializer = FollowSerializer(
                data={'user': user.id, 'author': author.id},
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            follow = serializer.save()
            serializer = FollowSerializer(follow, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        elif request.method == 'DELETE':
            if not user.follower.filter(author=author).exists():
                return Response(
                    {"detail": "Подписка не существует."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.follower.get(author=author).delete()
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

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return RecipeCreateUpdateSerializer
        return RecipeSerializer

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True,
            methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def favorite(self, request, pk=None):
        recipe = get_object_or_404(Recipe, id=pk)

        if request.method == 'POST':
            if request.user.favorites.filter(
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
            favorite = request.user.favorites.filter(recipe=recipe).first()
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
            if request.user.shopping_cart.filter(
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
            cart_item = request.user.shopping_cart.filter(recipe=recipe).first()
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
        shopping_cart = request.user.shopping_cart.all()
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
