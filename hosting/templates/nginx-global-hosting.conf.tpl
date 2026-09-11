# Сгенерировано {{PANEL_NAME}}. Подключить из http{} блока основного nginx.conf:
#   include /etc/nginx/conf.d/hosting-global.conf;
# Один общий файл с зонами limit_conn/limit_req — они должны быть объявлены один раз
# на весь http{}, отдельные vhost'ы только ссылаются на них (location { limit_req zone=... }).

limit_conn_zone $binary_remote_addr zone=perip_conn:20m;
limit_req_zone  $binary_remote_addr zone=general_req:20m rate=20r/s;
limit_req_zone  $binary_remote_addr zone=login_req:10m    rate=5r/m;

# Скрываем версию nginx в заголовках и на страницах ошибок
server_tokens off;

# Строгий лимит только на ОТПРАВКУ формы входа (POST), не на её открытие.
# nginx не считает запросы с пустым ключом, поэтому для GET лимит просто не
# применяется — а так на phpMyAdmin один лимит на весь сайт резал загрузку
# css/js, и интерфейс не открывался.
map $request_method $login_post_key {
    POST    $binary_remote_addr;
    default "";
}
limit_req_zone $login_post_key zone=login_post:10m rate=5r/m;
