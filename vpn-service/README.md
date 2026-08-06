# VPN Service (в разработке)

Инфраструктура для VPN-бизнеса: панель управления + Telegram-бот для продажи подписок.

## Компоненты

- **Панель:** [Marzban](https://github.com/Gozargah/Marzban) — управление клиентами, сроки подписки, лимиты трафика, API.
- **Протокол:** VLESS + Reality (обход блокировок).
- **Telegram-бот:** приём оплаты (Telegram Stars / CryptoBot) и автоматическая выдача подписок (в разработке, папка `bot/`).

## Установка панели (на сервере)

```bash
# 1. Установить Marzban (Docker ставится автоматически)
bash -c "$(curl -sL https://github.com/Gozargah/Marzban-scripts/raw/master/marzban.sh)" @ install

# 2. Создать администратора (логин/пароль для входа в панель)
marzban cli admin create --sudo

# 3. Открыть порт панели
ufw allow 8000/tcp 2>/dev/null || true

# 4. Проверить статус
marzban status
```

Панель доступна по адресу: `http://<SERVER_IP>:8000/dashboard/`

## Статус

- [x] Базовый VPN (WireGuard) — для личного использования
- [ ] Панель Marzban — установка
- [ ] Протокол VLESS + Reality
- [ ] Telegram-бот продажи подписок
