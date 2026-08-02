<?php
// Настройки для входа через Google (OAuth2).
// Получите Client ID и Client Secret в Google Cloud Console:
// https://console.cloud.google.com/apis/credentials
// Authorized redirect URI укажите: https://ваш-домен.com/auth/google_callback.php
// Если вход через Google не нужен, просто оставьте заглушки — кнопка на странице входа
// будет вести на страницу с понятной ошибкой, а логин/пароль продолжит работать.

define('GOOGLE_CLIENT_ID', 'your-client-id.apps.googleusercontent.com');
define('GOOGLE_CLIENT_SECRET', 'your-client-secret');
define('GOOGLE_REDIRECT_URI', 'https://ваш-домен.com/auth/google_callback.php');
