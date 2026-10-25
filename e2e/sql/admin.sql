-- Сценарии админ-панели: кто админ, роли, блокировки, решения по отзывам, отмена заказа, журнал.
-- Идёт после marketplace.sql на той же базе: магазин, товар, заказы и курьеры уже есть.
\set ON_ERROR_STOP on
\set QUIET on
\set S '''00000000-0000-0000-0000-00000000000a'''
\set B '''00000000-0000-0000-0000-00000000000b'''
\set K '''00000000-0000-0000-0000-00000000000c'''
\set K2 '''00000000-0000-0000-0000-00000000000d'''
\set B2 '''00000000-0000-0000-0000-00000000000e'''
\set A '''00000000-0000-0000-0000-0000000000ad'''

-- вход по номеру даёт служебную почту 992XXXXXXXXX@zud.tj; админ — обычная почта
update auth.users set email = '992900000010@zud.tj' where id = :S;
update auth.users set email = '992935550011@zud.tj' where id = :B;
update auth.users set email = '992900000001@zud.tj' where id = :K;
update auth.users set email = '992900000002@zud.tj' where id = :K2;
update auth.users set email = '992900000099@zud.tj' where id = :B2;
insert into auth.users (id, email) values (:A, 'owner@example.com');

-- ---------- доступ ----------
set role anon; select t.as_user(null);
select t.fails($$select admin_overview()$$, 'permission denied', 'гость не вызывает функции админа');
reset role;
set role authenticated; select t.as_user(:S);
select t.fails($$select admin_overview()$$, 'Нет доступа', 'продавец — не админ');
select t.ok((admin_me() ->> 'admin')::boolean = false, 'admin_me честно говорит «не админ»');
select t.fails($$insert into private.admins (user_id) values ('00000000-0000-0000-0000-00000000000a')$$, 'permission denied', 'стать админом самому нельзя');
reset role;
insert into private.admins (user_id, note) values (:A, 'владелец');

-- ---------- роли и связи ----------
select id as order1 from orders order by no limit 1 \gset
select id as shop_id from shops \gset
update shop_private set data = jsonb_build_object('staff', jsonb_build_array(jsonb_build_object('id', 'st1', 'name', 'Фарход', 'phone', '900000099', 'role', 'picker')))
  where shop_id = (select id from shops);
insert into shop_private (shop_id, data) select id, jsonb_build_object('staff', jsonb_build_array(jsonb_build_object('id', 'st1', 'name', 'Фарход', 'phone', '900000099', 'role', 'picker'))) from shops
  on conflict (shop_id) do nothing;
set role authenticated; select t.as_user(:A);
select t.ok((admin_me() ->> 'admin')::boolean, 'админ вошёл');
select t.ok((admin_overview() ->> 'users')::int = 6 and (admin_overview() ->> 'couriers')::int = 2, 'главный экран: люди и курьеры посчитаны');
select t.ok((select x -> 'roles' from jsonb_array_elements(admin_users()) x where x ->> 'id' = :S) ? 'seller', 'владелец магазина — роль «продавец»');
select t.ok((select x -> 'roles' from jsonb_array_elements(admin_users()) x where x ->> 'id' = :K) = '["courier"]'::jsonb, 'курьер — роль «курьер», и только она');
select t.ok((select x -> 'roles' from jsonb_array_elements(admin_users()) x where x ->> 'id' = :B) ? 'buyer', 'заказывал — роль «покупатель»');
select t.ok((select x -> 'roles' from jsonb_array_elements(admin_users()) x where x ->> 'id' = :B2) ? 'staff'
  and (select x ->> 'name' from jsonb_array_elements(admin_users()) x where x ->> 'id' = :B2) = 'Фарход', 'номер в списке сотрудников — роль «сотрудник» и имя');
select t.ok((select x -> 'roles' from jsonb_array_elements(admin_users()) x where x ->> 'id' = :A) ? 'admin', 'админ — роль «админ»');
select t.ok(jsonb_array_length(admin_users('93 555 00 11')) = 1, 'поиск человека по номеру с пробелами');
select t.ok(jsonb_array_length(admin_users('', 'courier')) = 2, 'фильтр по роли');
select t.ok(admin_user(:B) -> 'stats' ->> 'orders' = '2' and jsonb_array_length(admin_user(:K) -> 'deliveries') = 2, 'карточка человека: его заказы и доставки');
select t.ok(admin_user(:B2) -> 'staff_in' -> 0 ->> 'role' = 'picker', 'карточка сотрудника: в каком магазине и кем');
select t.ok(admin_shop(:'shop_id') -> 'staff' -> 0 -> 'user' ->> 'id' = :B2, 'магазин: сотрудник связан со своей учётной записью');
select t.ok(admin_shop(:'shop_id') -> 'owner' ->> 'phone' = '900000010', 'магазин: владелец и его номер');
select t.ok(jsonb_array_length(admin_orders('done')) >= 1 and jsonb_array_length(admin_orders('', '935550011')) = 2, 'заказы: фильтр по статусу и номеру покупателя');
select t.ok((admin_order(:'order1') ->> 'code') ~ '^\d{4}$', 'заказ: админ видит код получения (для поддержки)');
select t.ok(jsonb_typeof(admin_checks()) = 'array' and jsonb_typeof(admin_map() -> 'couriers') = 'array', 'проверки и карта отвечают');
select t.fails(format('select admin_set_admin(%L, true)', :S), 'по почте и паролю', 'учётку по номеру без SMS нельзя сделать админом');
select t.fails(format('select admin_set_admin(%L, false)', :A), 'Себя снять нельзя', 'последний админ не снимет сам себя');
select t.fails(format('select admin_user_block(%L, true, %L)', :A, 'тест'), 'самого себя', 'себя не заблокировать');
reset role;

-- ---------- блокировка магазина ----------
set role authenticated; select t.as_user(:A);
select t.fails(format('select admin_shop_block(%L, true, %L)', :'shop_id', ''), 'причину', 'блокировка без причины не проходит');
select admin_shop_block(:'shop_id', true, 'Продаёт запрещённое');
reset role;
set role authenticated; select t.as_user(:S);
select t.fails($$update shops set blocked = false$$, 'только администратор', 'владелец не снимет блокировку сам');
select t.ok((select blocked and block_reason = 'Продаёт запрещённое' from shops), 'владелец видит свой магазин и причину');
update shops set about = 'новое описание';
select t.ok((select blocked from shops), 'обычное сохранение магазина не снимает блокировку');
reset role;
set role anon; select t.as_user(null);
select t.ok((select count(*) from shops) = 0 and (select count(*) from products) = 0, 'покупатель не видит заблокированный магазин и его товары');
reset role;
set role authenticated; select t.as_user(:B);
select t.fails(format($$select place_order(%L, '[{"pid":"p-tomato","qty":1}]', '{}', 'М', '+992 935550011')$$, :'shop_id'), 'не принимает заказы', 'в заблокированный магазин не заказать');
reset role;
set role authenticated; select t.as_user(:A);
select admin_shop_block(:'shop_id', false);
reset role;
set role anon; select t.as_user(null);
select t.ok((select count(*) from shops) = 1, 'разблокировали — магазин снова виден');
reset role;

-- ---------- блокировка товара ----------
set role authenticated; select t.as_user(:A);
select admin_product_block('p-tomato', true, 'Нет сертификата');
reset role;
set role anon; select t.as_user(null);
select t.ok((select count(*) from products) = 0, 'скрытый товар не виден покупателю');
reset role;
set role authenticated; select t.as_user(:S);
insert into products (id, shop_id, name, price, blocked) values ('p-new', :'shop_id', 'Огурцы', 10, true) on conflict (id) do update set stock = 5;
select t.ok((select not blocked from products where id = 'p-new'), 'магазин не создаст товар сразу «заблокированным» в обход админа');
select t.fails($$update products set blocked = false where id = 'p-tomato'$$, 'только администратор', 'магазин не вернёт скрытый товар сам');
insert into products (id, shop_id, name, price, stock) values ('p-tomato', :'shop_id', 'Помидоры', 12, 40) on conflict (id) do update set stock = 41;
select t.ok((select blocked from products where id = 'p-tomato'), 'сохранение товара (upsert) не снимает блокировку');
reset role;
set role authenticated; select t.as_user(:A);
select admin_product_block('p-tomato', false);
reset role;

-- ---------- блокировка человека целиком ----------
set role authenticated; select t.as_user(:A);
select admin_courier_block(:K2, true, 'Грубил покупателю');
select admin_user_block(:K2, true, 'Обман');
select admin_user_block(:B, true, 'Фейковые заказы');
reset role;
set role authenticated; select t.as_user(:B);
select t.fails(format($$select place_order(%L, '[{"pid":"p-tomato","qty":1}]', '{}', 'М', '+992 935550011')$$, :'shop_id'), 'ограничен администратором', 'заблокированный покупатель не может заказать');
select t.fails($$insert into shops (name, kind) values ('Второй', 'grocery')$$, 'ограничен администратором', 'заблокированный не откроет магазин');
reset role;
set role authenticated; select t.as_user(:K2);
select t.fails($$select courier_feed()$$, 'приостановлен', 'заблокированный курьер не видит заказы');
reset role;
set role authenticated; select t.as_user(:A);
select admin_user_block(:B, false);
select admin_user_block(:K2, false);
reset role;
select t.ok((select status = 'blocked' and block_reason = 'Грубил покупателю' from couriers where id = :K2),
  'сняли блокировку человека — отдельная блокировка курьера осталась как была');
set role authenticated; select t.as_user(:A);
select admin_courier_block(:K2, false);
reset role;
set role authenticated; select t.as_user(:K2);
select t.ok(jsonb_typeof(courier_feed()) = 'array', 'разблокированный курьер снова работает');
reset role;

-- ---------- отзывы: решение только у админа ----------
set role authenticated; select t.as_user(:B);
select buyer_review(:'order1', 2, '{}', 'Помидоры мятые', '{}'::jsonb, 'Мадина');
reset role;
select t.ok((select rating = 2 and rating_count = 1 from shops), 'отзыв посчитан в рейтинге магазина');
set role authenticated; select t.as_user(:S);
update reviews set complaint = '{"reason": "Неправда", "status": "review", "hidden": true}';
select t.ok((select bool_and(not (complaint ? 'hidden')) from reviews), 'магазин может пожаловаться, но не скрыть отзыв сам');
reset role;
select id as review_id from reviews order by created_at limit 1 \gset
set role authenticated; select t.as_user(:A);
select admin_review_decide(:'review_id', true, 'Оскорбление');
reset role;
set role authenticated; select t.as_user(:S);
update reviews set complaint = '{"reason": "ещё раз", "status": "review"}', reply = 'Спасибо' where id = :'review_id';
select t.ok((select complaint ->> 'status' = 'accepted' and (complaint ->> 'hidden')::boolean and reply = 'Спасибо' from reviews where id = :'review_id'),
  'после решения админа магазин отвечает на отзыв, но решение не переписать');
reset role;
set role anon; select t.as_user(null);
select t.ok(not exists (select 1 from reviews where id = :'review_id'), 'скрытый отзыв не виден покупателям');
reset role;
select t.ok((select rating_count = 0 from shops), 'скрытый отзыв не считается в рейтинге');

-- ---------- заказ: отмена админом возвращает остаток ----------
set role authenticated; select t.as_user(:B);
select id as order3 from place_order(:'shop_id', '[{"pid":"p-tomato","qty":3}]', '{}', 'Мадина', '+992 935550011') \gset
reset role;
select stock as stock_before from products where id = 'p-tomato' \gset
set role authenticated; select t.as_user(:A);
select t.fails(format('select admin_order_cancel(%L, %L)', :'order3', ''), 'причину', 'отмена без причины не проходит');
select admin_order_cancel(:'order3', 'Покупатель позвонил в поддержку');
select t.fails(format('select admin_order_cancel(%L, %L)', :'order3', 'ещё'), 'уже отменён', 'дважды не отменить');
reset role;
select t.ok((select stock from products where id = 'p-tomato') = :stock_before + 3, 'отмена админом вернула остаток');
select t.ok((select cancel_reason from orders where id = :'order3') like 'Отменил администратор:%', 'покупатель и магазин видят, кто отменил');
set role authenticated; select t.as_user(:A);
select t.ok(jsonb_array_length(admin_log()) >= 10, 'каждое действие админа записано в журнал');
select t.ok(admin_log() -> 0 ->> 'by' = 'owner@example.com', 'в журнале видно, какой админ');
reset role;
\echo OK sql: админ-панель — все проверки прошли
