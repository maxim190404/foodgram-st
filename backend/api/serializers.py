from rest_framework import serializers
from django.contrib.auth import get_user_model
from djoser.serializers import UserSerializer as DjoserUserSerializer
from djoser.serializers import (UserCreateSerializer as
                                DjoserUserCreateSerializer)
from users.models import Follow
from recipes.models import (Ingredient, Recipe, RecipeIngredient,
                            ShoppingCart, Favorite)
from django.core.files.base import ContentFile
import base64
import uuid

User = get_user_model()


class Base64ImageField(serializers.ImageField):
    def to_representation(self, value):
        if value and hasattr(value, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(value.url)
        return ''

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(
                base64.b64decode(imgstr),
                name=f'{uuid.uuid4()}.{ext}'
            )
        return super().to_internal_value(data)


class CustomUserCreateSerializer(DjoserUserCreateSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name',
                  'last_name', 'password')
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True}
        }


class CustomUserSerializer(DjoserUserSerializer):
    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name', 'last_name',
                  'is_subscribed', 'avatar')

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Follow.objects.filter(user=request.user,
                                         author=obj).exists()
        return False

    def get_avatar(self, obj):
        if obj.avatar and hasattr(obj.avatar, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
        return ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data['avatar'] is None:
            data['avatar'] = ''
        return data


class SetAvatarSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('avatar',)

    def get_avatar(self, obj):
        if obj.avatar:
            with open(obj.avatar.path, 'rb') as image_file:
                image_data = base64.b64encode(
                    image_file.read()).decode('utf-8')
            image_mime_type = self.context.get('mime_type', 'image/jpeg')
            return f'data:{image_mime_type};base64,{image_data}'
        return None


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='ingredient.id')
    name = serializers.CharField(source='ingredient.name', read_only=True)
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit', read_only=True)

    def validate(self, data):
        ingredient_id = data['ingredient']['id']
        if not Ingredient.objects.filter(id=ingredient_id).exists():
            raise serializers.ValidationError(
                {
                    'ingredient':
                        (f'Ингредиент с ID {ingredient_id} не существует')}
            )
        return data

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeSerializer(serializers.ModelSerializer):
    author = CustomUserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(source='recipe_ingredients',
                                             many=True)
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'author', 'name', 'image', 'text', 'ingredients',
            'cooking_time', 'is_favorited', 'is_in_shopping_cart'
        )

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(user=request.user,
                                           recipe=obj).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ShoppingCart.objects.filter(user=request.user,
                                               recipe=obj).exists()
        return False

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError(
                'Необходимо указать хотя бы один ингредиент.')

        ingredient_ids = [item['ingredient']['id'] for item in value]

        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                'Один и тот же ингредиент не должен повторяться.')

        existing_ids = set(Ingredient.objects.filter(
            id__in=ingredient_ids
        ).values_list('id', flat=True))

        for ingredient_id in ingredient_ids:
            if ingredient_id not in existing_ids:
                raise serializers.ValidationError(
                    f'Ингредиент с ID {ingredient_id} не существует'
                )
        return value

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        ingredients_data = validated_data.pop('recipe_ingredients')
        recipe = Recipe.objects.create(**validated_data)

        for ingredient_data in ingredients_data:
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient_id=ingredient_data['ingredient']['id'],
                amount=ingredient_data['amount']
            )
        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('recipe_ingredients', None)
        instance = super().update(instance, validated_data)
        if ingredients_data is not None:
            instance.recipe_ingredients.all().delete()
            for ingredient_data in ingredients_data:
                RecipeIngredient.objects.create(
                    recipe=instance,
                    ingredient_id=ingredient_data['ingredient']['id'],
                    amount=ingredient_data['amount']
                )
        return instance


class RecipeMinifiedSerializer(serializers.ModelSerializer):
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class UserWithRecipesSerializer(CustomUserSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()
    is_subscribed = serializers.SerializerMethodField()

    class Meta(CustomUserSerializer.Meta):
        fields = CustomUserSerializer.Meta.fields + (
            'recipes', 'recipes_count', 'is_subscribed')

    def get_recipes(self, obj):
        request = self.context.get('request')
        limit = request.query_params.get('recipes_limit') if request else None
        queryset = obj.recipes.all()
        if limit:
            queryset = queryset[:int(limit)]
        return RecipeMinifiedSerializer(queryset, many=True).data

    def get_recipes_count(self, obj):
        return obj.recipes.count()

    def get_is_subscribed(self, obj):
        return True


class FavoriteSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='recipe.id')
    name = serializers.ReadOnlyField(source='recipe.name')
    image = serializers.SerializerMethodField()
    cooking_time = serializers.ReadOnlyField(source='recipe.cooking_time')

    class Meta:
        model = Favorite
        fields = ('id', 'name', 'image', 'cooking_time')

    def get_image(self, obj):
        if obj.recipe.image and hasattr(obj.recipe.image, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.recipe.image.url)


class ShoppingCartSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='recipe.id')
    name = serializers.ReadOnlyField(source='recipe.name')
    image = serializers.SerializerMethodField()
    cooking_time = serializers.ReadOnlyField(source='recipe.cooking_time')

    class Meta:
        model = ShoppingCart
        fields = ('id', 'name', 'image', 'cooking_time')

    def get_image(self, obj):
        if obj.recipe.image and hasattr(obj.recipe.image, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.recipe.image.url)


class FollowSerializer(serializers.ModelSerializer):
    email = serializers.ReadOnlyField(source='author.email')
    id = serializers.ReadOnlyField(source='author.id')
    username = serializers.ReadOnlyField(source='author.username')
    first_name = serializers.ReadOnlyField(source='author.first_name')
    last_name = serializers.ReadOnlyField(source='author.last_name')
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = Follow
        fields = (
            'email', 'id', 'username', 'first_name', 'last_name',
            'is_subscribed', 'recipes', 'recipes_count', 'avatar'
        )

    def get_is_subscribed(self, obj):
        return True

    def get_recipes(self, obj):
        request = self.context.get('request')
        limit = request.query_params.get('recipes_limit') if request else None
        queryset = obj.author.recipes.all()
        if limit:
            queryset = queryset[:int(limit)]
        return RecipeMinifiedSerializer(queryset, many=True).data

    def get_recipes_count(self, obj):
        return obj.author.recipes.count()

    def get_avatar(self, obj):
        if obj.author.avatar and hasattr(obj.author.avatar, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.author.avatar.url)


class SetPasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Текущий пароль неверен')
        return value


class RecipeCreateResponseSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    author = CustomUserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        many=True, source='recipe_ingredients')
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ('id', 'author', 'ingredients', 'is_favorited',
                  'is_in_shopping_cart', 'name', 'image', 'text',
                  'cooking_time')

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(
                user=request.user, recipe=obj).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ShoppingCart.objects.filter(
                user=request.user, recipe=obj).exists()
        return False


class RecipeUpdateSerializer(RecipeCreateResponseSerializer):
    ingredients = RecipeIngredientSerializer(
        source='recipe_ingredients',
        many=True,
        required=True
    )
    image = Base64ImageField(required=False)

    class Meta(RecipeCreateResponseSerializer.Meta):
        extra_kwargs = {
            'name': {'required': False},
            'text': {'required': False},
            'cooking_time': {'required': False}
        }

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError({
                'ingredients': [
                    {},
                    {'amount': [
                        'Убедитесь, что это значение больше либо равно 1.']},
                    {}
                ]
            })
        ingredient_ids = [item['ingredient']['id'] for item in value]

        existing_count = Ingredient.objects.filter(
            id__in=ingredient_ids
        ).count()

        if existing_count != len(ingredient_ids):
            raise serializers.ValidationError(
                'Один или несколько ингредиентов не существуют'
            )

        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                'Ингредиенты должны быть уникальными.')
        return value

    def update(self, instance, validated_data):
        if 'recipe_ingredients' not in validated_data:
            raise serializers.ValidationError({
                'ingredients': [
                    {},
                    {'amount': [
                        'Убедитесь, что это значение больше либо равно 1.']},
                    {}
                ]
            })
        ingredients_data = validated_data.pop('recipe_ingredients')

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.recipe_ingredients.all().delete()
        for ingredient_data in ingredients_data:
            RecipeIngredient.objects.create(
                recipe=instance,
                ingredient_id=ingredient_data['ingredient']['id'],
                amount=ingredient_data['amount']
            )
        instance.save()
        return instance
