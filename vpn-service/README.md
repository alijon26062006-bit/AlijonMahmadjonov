# VPN Service (Marzban + Reality + Telegram bot)

Инфраструктура и автоматизация для VPN-сервиса с продажей подписок через Telegram.

> ⚠️ **Секреты (ключи, пароли, токены) в репозиторий не коммитим.** Здесь только
> шаблоны и документация. Реальные значения живут на сервере в `.env` и в конфигах
> Marzban.

## Компоненты

| Слой | Технология | Роль |
|------|-----------|------|
| Панель управления | **Marzban** (Docker) | Клиенты, сроки подписки, лимиты трафика, API |
| Протокол | **VLESS + Reality + Vision** | Обход DPI/блокировок (маскировка под реальный сайт) |
| Доступ к панели | **nginx** (reverse proxy) | Проброс панели наружу на порт `8080` |
| Резервный протокол | **WireGuard** | Запасной канал (не основной для РФ) |
| Продажи | **Telegram-бот** (aiogram) | Приём оплаты и авто-выдача подписок |

## Порты

| Порт | Назначение |
|------|-----------|
| `443/tcp` | VLESS Reality (основной VPN-трафик) |
| `8080/tcp` | Панель Marzban (через nginx) |
| `8000` | Marzban (только localhost, наружу не смотрит) |
| `51820/udp` | WireGuard (резерв) |

## Установка на сервере (Debian)

### 1. Marzban
```bash
bash -c "$(curl -sL https://github.com/Gozargah/Marzban-scripts/raw/master/marzban.sh)" @ install
marzban cli admin create --sudo   # задать логин/пароль администратора
```

### 2. Доступ к панели через nginx
Проксируем локальный порт `8000` наружу на `8080`. Панель:
`http://<SERVER_IP>:8080/dashboard/`

### 3. Reality (защита от блокировок)
Ключи генерируются на сервере:
```bash
docker exec $(docker ps -qf name=marzban) xray x25519   # privateKey / publicKey
openssl rand -hex 8                                       # shortId
```
Свой `privateKey` подставляется в `/var/lib/marzban/xray_config.json`
(инбаунд VLESS Reality на порту 443), затем `marzban restart`.

**Почему Reality:** DPI (ТСПУ) распознаёт VPN по сигнатуре трафика. Reality
маскирует соединение под обычный HTTPS-заход на крупный иностранный сайт (SNI),
поэтому не детектируется. Основной протокол для РФ — только Reality на порту 443.

### 4. Telegram-бот
Каталог `bot/` — бот на aiogram, подключается к API Marzban, принимает оплату
(Telegram Stars / CryptoBot) и автоматически создаёт/продлевает подписки.
Конфигурация — через `.env` (см. `bot/.env.example`, будет добавлен).

## План развития
- [x] WireGuard (резервный VPN)
- [x] Marzban + панель через nginx
- [x] Reality (анти-блокировка)
- [ ] Домен + Cloudflare + SSL для ссылок-подписок
- [ ] Telegram-бот: тарифы, оплата, авто-выдача
- [ ] Резервный сервер (масштабирование)
