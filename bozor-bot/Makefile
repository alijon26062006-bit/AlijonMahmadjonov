.PHONY: up down logs seed psql build

up:            ## Запустить всё
	docker compose up -d --build

down:          ## Остановить
	docker compose down

logs:          ## Логи бота и API
	docker compose logs -f bot api worker

seed:          ## Пересоздать справочники
	docker compose run --rm migrate

psql:          ## Консоль БД
	docker compose exec db psql -U bozor -d bozor

build:         ## Пересобрать образы
	docker compose build
