import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from recipes.models import Ingredient


class Command(BaseCommand):
    help = "Загружает данные об ингредиентах из JSON-файла в базу данных"

    def handle(self, *args, **options):
        file_path = Path(settings.BASE_DIR) / "data" / "ingredients.json"
        if not file_path.exists():
            self.stdout.write(
                self.style.ERROR(f"Файл не найден: {file_path}")
            )
            return
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                ingredients_data = json.load(file)
                ingredients = [
                    Ingredient(**item) for item in ingredients_data
                ]
                before_count = Ingredient.objects.count()
                Ingredient.objects.bulk_create(
                    ingredients,
                    ignore_conflicts=True
                )
                created_count = Ingredient.objects.count() - before_count
                self.stdout.write(
                    self.style.SUCCESS(
                        f" Успешно загружено {created_count} ингредиентов"
                    )
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Ошибка при загрузке данных: {str(e)}")
            )
