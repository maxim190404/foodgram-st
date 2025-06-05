# Foodgram

## Описание проекта

«Фудграм» — сервис предназначенный для публикации рецептов пользователей, а также для добавления рецептов в избранное, список покупок, скачивания списка покупок, подписки на других пользователей.

## Как запустить проект

Клонировать репозиторий и перейти в него в команддной строке :

```bash
git clone https://github.com/maxim190404/foodgram-st.git 
```

```bash
cd foodgram-st
```

Запустить docker compose:
```bash
cd infra
```
В каталоге `infra` необходимо создать файл `.env`, который заполняется согласно примеру
```
POSTGRES_USER=django
POSTGRES_PASSWORD=<your_password>
POSTGRES_DB=django
DB_HOST=db
DB_PORT=5432
SECRET_KEY=<your_secret_key>
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
DEBUG=False
```


```bash
docker compose up --build
```

Далее выполнит миграции внутри БД:

```bash
docker compose exec backend python manage.py migrate
```

Загрузить статику:

```bash
docker compose exec backend python manage.py collectstatic
```

Загрузить в БД ингредиенты:

```bash
docker compose exec backend python manage.py load_bd
```


### Доступы:
`Главная страница` - `http://localhost:8000/`

`Админка` - `http://localhost:8000/admin/`

`Документация` - `http://localhost:8000//api/docs/`



### Автор

[Ходаков Максим](mailto:mxkhodakov@yandex.ru)