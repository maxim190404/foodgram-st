from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import CustomUser as User
from shortuuid import uuid

MIN_COOKING_TIME = 1
MAX_COOKING_TIME = 32000


class Ingredient(models.Model):
    name = models.CharField(
        max_length=128,
        verbose_name='Название ингредиента',
        help_text='Введите название ингредиента'
    )
    measurement_unit = models.CharField(
        verbose_name='Единица измерения',
        max_length=64,
        help_text='Введите единицу измерения (г, мл, шт. и т.д.)'
    )

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'

    def __str__(self):
        return f"{self.name} ({self.measurement_unit})"


class Recipe(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recipes',
        verbose_name='Автор рецепта блюда'
    )
    name = models.CharField(
        max_length=256,
        verbose_name='Название блюда',
        help_text='Введите название блюда'
    )
    image = models.ImageField(
        verbose_name='Изображение',
        upload_to='recipes/images/',
        help_text='Загрузите изображение рецепта'
    )
    text = models.TextField(
        verbose_name='Описание блюда',
        help_text='Введите описание рецепта'
    )
    ingredients = models.ManyToManyField(
        Ingredient,
        verbose_name='Ингредиенты',
        related_name='recipes',
        through='RecipeIngredient'
    )
    cooking_time = models.PositiveSmallIntegerField(
        verbose_name='Время приготовления (в минутах)',
        validators=[
            MinValueValidator(MIN_COOKING_TIME),
            MaxValueValidator(MAX_COOKING_TIME)
    ]
    )
    pub_date = models.DateTimeField(
        verbose_name='Дата публикации',
        auto_now_add=True
    )
    short_link = models.CharField(
        max_length=32,
        unique=True,
        default=uuid,
        verbose_name='Короткая ссылка',
        help_text='Уникальная короткая ссылка для рецепта'
    )

    class Meta:
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        ordering = ['-pub_date']

    def __str__(self):
        return self.name


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт блюда',
        related_name='recipe_ingredients'
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name='ingredient_recipes',
        verbose_name='Ингредиент'
    )
    amount = models.PositiveSmallIntegerField(
        verbose_name='Количество ингредиентов',
                validators=[
            MinValueValidator(MIN_COOKING_TIME),
            MaxValueValidator(MAX_COOKING_TIME)
    ],
        help_text='Укажите количество ингредиентов (минимум 1)'
    )

    class Meta:
        verbose_name = 'Ингредиент в рецепте'
        verbose_name_plural = 'Ингредиенты в рецептах'
        unique_together = ('recipe', 'ingredient')

    def __str__(self):
        return (f"{self.ingredient.name} - "
                f"{self.amount} {self.ingredient.measurement_unit}")


class ShoppingCart(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shopping_cart',
        verbose_name='Пользователь'
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='in_cart',
        verbose_name='Рецепт'
    )

    class Meta:
        verbose_name = 'Список покупок'
        verbose_name_plural = 'Списки покупок'
        unique_together = ('user', 'recipe')

    def __str__(self):
        return f"{self.user} добавил {self.recipe} в покупки"


class Favorite(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name='Пользователь'
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='favorited_by',
        verbose_name='Рецепт'
    )

    class Meta:
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'

    def __str__(self):
        return f"{self.user} добавил {self.recipe} в избранное"
