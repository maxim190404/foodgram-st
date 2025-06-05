from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator


class CustomUser(AbstractUser):
    email = models.EmailField(
        max_length=254,
        unique=True,
        verbose_name='Адрес электронной почты',
        help_text='Введите адрес электронной почты'
    )
    username = models.CharField(
        max_length=150,
        unique=True,
        verbose_name='Никнейм',
        help_text='Введите никнейм',
        validators=[
            RegexValidator(
                regex=r'^[\w.@+-]+\Z'
            )
        ]
    )
    first_name = models.CharField(
        max_length=150,
        verbose_name='Имя',
        help_text='Введите имя',
        blank=False
    )
    last_name = models.CharField(
        max_length=150,
        verbose_name='Фамилия',
        help_text='Введите фамилию',
        blank=False
    )
    avatar = models.ImageField(
        upload_to='users/avatars/',
        null=True,
        blank=True,
        verbose_name='Аватар',
        help_text='Загрузите изображение аватара'
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username


class Follow(models.Model):
    user = models.ForeignKey(
        'CustomUser',
        on_delete=models.CASCADE,
        related_name='follower',
        verbose_name='Подписчик',
        help_text='Пользователь, который подписывается'
    )
    author = models.ForeignKey(
        'CustomUser',
        on_delete=models.CASCADE,
        related_name='following',
        verbose_name='Автор',
        help_text='Пользователь, на которого подписываются'
    )

    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        constraints = [
            models.UniqueConstraint(fields=['user', 'author'],
                                    name='unique_follow'),
            models.CheckConstraint(
                check=~models.Q(user=models.F('author')),
                name='prevent_self_follow'
            )
        ]

    def __str__(self):
        return f"{self.user} подписан на {self.author}"
