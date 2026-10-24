-- Сценарии базы маркетплейса: заказ, цены, права, курьер. Каждая проверка либо проходит, либо останавливает прогон с понятной причиной.
\set ON_ERROR_STOP on
\set QUIET on
create schema t;
-- войти как пользователь (как это делает Supabase по токену)
create function t.as_user(uid uuid) returns void language sql as $$ select set_config('request.jwt.claim.sub', uid::text, false); $$;
create function t.ok(cond boolean, what text) returns void language plpgsql as $$
begin if cond is not true then raise exception 'НЕ ВЫПОЛНЕНО: %', what; end if; raise notice 'ok — %', what; end $$;
-- запрос должен упасть с ошибкой, в тексте которой есть pat
create function t.fails(q text, pat text, what text) returns void language plpgsql as $$
declare err text;
begin
  begin execute q; exception when others then err := sqlerrm; end;
  if err is null then raise exception 'НЕ ВЫПОЛНЕНО: % — запрос прошёл, а должен был отказать', what; end if;
  if strpos(err, pat) = 0 then raise exception 'НЕ ВЫПОЛНЕНО: % — ждали «%», получили «%»', what, pat, err; end if;
  raise notice 'ok — %', what;
end $$;
grant usage on schema t to anon, authenticated; grant execute on all functions in schema t to anon, authenticated;

insert into auth.users values ('00000000-0000-0000-0000-00000000000a', 's@x'), ('00000000-0000-0000-0000-00000000000b', 'b@x'),
  ('00000000-0000-0000-0000-00000000000c', 'k@x'), ('00000000-0000-0000-0000-00000000000d', 'k2@x'), ('00000000-0000-0000-0000-00000000000e', 'b2@x');
\set S '''00000000-0000-0000-0000-00000000000a'''
\set B '''00000000-0000-0000-0000-00000000000b'''
\set K '''00000000-0000-0000-0000-00000000000c'''
\set K2 '''00000000-0000-0000-0000-00000000000d'''
\set B2 '''00000000-0000-0000-0000-00000000000e'''

-- ---------- продавец: магазин и товар ----------
set role authenticated; select t.as_user(:S);
insert into shops (name, kind, lat, lng, city, address, min_order) values ('Бозори Сабз', 'grocery', 43.2389, 76.8897, 'Алматы', 'Абая 1', 10);
insert into products (id, shop_id, name, price, stock, unit, cat) select 'p-tomato', id, 'Помидоры', 12, 40, 'кг', 'Овощи и зелень' from shops;
select t.ok((select sku from products) = 100001, 'артикул товара — цифры с 100001');
reset role;

-- ---------- покупатель: заказ считает база ----------
set role authenticated; select t.as_user(:B);
select t.fails($$select place_order((select id from shops), '[{"pid":"p-tomato","qty":100}]', '{"lat":43.2489,"lng":76.8997}', 'М', '+992 935550011', 'cash')$$, 'Осталось только', 'нельзя заказать больше остатка');
select t.fails($$select place_order((select id from shops), '[{"pid":"p-tomato","qty":0.5}]', '{"lat":43.2489,"lng":76.8997}', 'М', '+992 935550011', 'cash')$$, 'Минимальный заказ', 'минимальная сумма заказа');
select no as order_no, total as order_total, fee as order_fee from place_order((select id from shops), '[{"pid":"p-tomato","qty":2,"price":1}]',
  '{"city":"Алматы","street":"Абая","house":"10","lat":43.2489,"lng":76.8997}', 'Мадина', '+992 935550011', 'cash') \gset
select t.ok(:order_total = 24 + 15, 'цену берёт база, а не телефон (2 × 12 + доставка 15 до 2 км)');
reset role;
select t.ok((select stock from products) = 38, 'остаток уменьшился на заказ');
select t.ok((select ok from private.delivery_quote(43.2389, 76.8897, null, null)), 'открытая зона: покупатель без метки — рядом с магазином');
select t.ok(not (select ok from private.delivery_quote(43.2389, 76.8897, 51.1694, 71.4491)), 'Алматы → Астана: слишком далеко');

-- ---------- чужие заказы не видны ----------
set role authenticated; select t.as_user(:B2);
select t.ok((select count(*) from orders) = 0, 'другой покупатель не видит чужой заказ');
reset role;
set role anon; select t.as_user(null);
select t.ok((select count(*) from orders) = 0, 'гость без входа не видит ни одного заказа');
reset role;

-- ---------- курьеры ----------
set role authenticated; select t.as_user(:K);
select t.fails($$select courier_feed()$$, 'анкету курьера', 'лента — только после анкеты');
select courier_register('Алишер', '+992 900000001', 'Opel Astra, белый', '01 123 aa') \g /dev/null
select courier_online(true, 43.24, 76.89) \g /dev/null
select t.ok(courier_feed() = '[]'::jsonb, 'курьер не видит заказ, пока магазин не принял');
reset role;
set role authenticated; select t.as_user(:K2);
select courier_register('Бахром', '+992 900000002', 'Toyota', '02 555 BB') \g /dev/null
select courier_online(true, 43.3, 76.95) \g /dev/null
reset role;
set role authenticated; select t.as_user(:S);
update orders set status = 'accepted', accepted_at = now(), ready_in = 10;
select t.fails($$update orders set courier_id = '00000000-0000-0000-0000-00000000000c'$$, 'только из приложения курьера', 'магазин не может сам назначить курьера');
reset role;
set role authenticated; select t.as_user(:K);
select t.ok(jsonb_array_length(courier_feed()) = 1, 'принятый заказ появился в ленте курьера');
select t.ok((courier_feed() -> 0 ->> 'earn')::numeric = 15, 'в ленте видно, сколько заработает курьер');
select t.ok(courier_feed() -> 0 -> 'phone' is null and courier_feed() -> 0 ->> 'area' = 'Алматы, Абая', 'до «Беру» телефон и точный адрес скрыты');
select courier_feed() -> 0 ->> 'id' as order_id \gset
reset role;
set role authenticated; select t.as_user(:K);
select t.ok(courier_take(:'order_id') ->> 'step' = 'going', '«Беру» — заказ достался курьеру');
reset role;
set role authenticated; select t.as_user(:K2);
select t.fails(format('select courier_take(%L)', :'order_id'), 'уже взял другой курьер', 'второй курьер не перехватит заказ');
select t.ok((select count(*) from orders) = 0, 'второй курьер не видит чужую доставку');
select t.ok(buyer_code(:'order_id') is null and order_courier_where(:'order_id') is null, 'чужой курьер не видит код и место');
reset role;
set role authenticated; select t.as_user(:B);
select t.ok((select courier ->> 'plate' from orders) = '01 123 AA', 'покупатель видит курьера и номер машины');
select t.ok(buyer_code(:'order_id') ~ '^\d{4}$', 'у покупателя есть 4-значный код');
select t.ok(order_courier_where(:'order_id') ->> 'lat' is not null, 'покупатель видит, где курьер');
reset role;
set role authenticated; select t.as_user(:K);
update orders set courier_fee = 999;   -- правила доступа не дают курьеру менять заказ напрямую: 0 строк
select t.ok((select courier_fee from orders where id = :'order_id') = 15, 'курьер не может сам поменять свой заработок');
select t.ok(courier_step(:'order_id', 'at_shop') ->> 'step' = 'at_shop', 'курьер в магазине');
select t.ok(courier_step(:'order_id', 'picked') ->> 'status' = 'done', 'забрал — заказ «в пути»');
select t.fails(format('select courier_step(%L, %L, %L)', :'order_id', 'delivered', '0000'), 'Код не подходит', 'неверный код не закрывает заказ');
reset role;
select code as order_code from private.order_codes \gset
set role authenticated; select t.as_user(:K);
select t.ok((courier_step(:'order_id', 'delivered', :'order_code') ->> 'cash_taken')::numeric = :order_total, 'верный код — доставлено, наличные записаны');
reset role;
set role authenticated; select t.as_user(:B);
select buyer_rate_courier(:'order_id', 5) \g /dev/null
select buyer_rate_courier(:'order_id', 1) \g /dev/null
reset role;
select t.ok((select rating = 5 and rating_count = 1 from couriers where name = 'Алишер'), 'оценка курьера — одна на заказ');

-- отказ до забора: заказ снова свободен
set role authenticated; select t.as_user(:B);
select no from place_order((select id from shops), '[{"pid":"p-tomato","qty":1}]', '{"city":"Алматы","street":"Абая","house":"12"}', 'Мадина', '+992 935550011', 'card') \g /dev/null
reset role;
set role authenticated; select t.as_user(:S);
update orders set status = 'ready' where status = 'new';
reset role;
set role authenticated; select t.as_user(:K2);
select (courier_take(courier_feed() -> 0 ->> 'id') ->> 'id') as order2 \gset
select courier_release(:'order2') \g /dev/null
select t.ok(jsonb_array_length(courier_feed()) = 1, 'отказался — заказ снова в ленте');
reset role;
set role authenticated; select t.as_user(:K);
select courier_take(:'order2') \g /dev/null
select courier_step(:'order2', 'picked') \g /dev/null
reset role;
set role authenticated; select t.as_user(:B);
select buyer_received(:'order2');
reset role;
select t.ok((select courier_status = 'delivered' and received_at is not null from orders where id = :'order2'), 'покупатель сам нажал «Получил» — доставка закрыта');
set role anon; select t.as_user(null);
select t.fails($$select courier_feed()$$, 'permission denied', 'гость не вызывает функции курьера');
reset role;
\echo OK sql: все проверки базы прошли
