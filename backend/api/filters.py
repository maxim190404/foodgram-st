from django_filters import rest_framework as filters
from recipes.models import Recipe
from django.contrib.auth import get_user_model

User = get_user_model()


class RecipeFilter(filters.FilterSet):
    is_favorited = filters.BooleanFilter(method='filter_favorited')
    is_in_shopping_cart = filters.BooleanFilter(method='filter_shopping_cart')
    author = filters.NumberFilter(field_name='author__id')

    class Meta:
        model = Recipe
        fields = ['author']

    def filter_favorited(self, queryset, name, value):
        user = self.request.user
        if value and user.is_authenticated:
            return queryset.filter(favorited_by__user=user)
        return queryset

    def filter_shopping_cart(self, queryset, name, value):
        user = self.request.user
        if value and user.is_authenticated:
            return queryset.filter(in_cart__user=user)
        return queryset
