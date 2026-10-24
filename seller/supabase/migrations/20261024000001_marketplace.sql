-- Маркетплейс «Зуд»: магазины, товары с цифровым артикулом, заказы покупателей, отзывы, расходы, фото.
-- Заменяет первую схему кабинета (её таблицы были пустыми).
--
-- Кто что видит:
--   * каталог (магазины, товары в продаже, отзывы) — все, даже без входа;
--   * закупочные цены, Alif, сотрудники, расходы — только владелец магазина;
--   * заказ — покупатель, который его сделал, и магазин, которому он адресован.
-- Покупатель не может сам вписать цену: заказ создаёт функция place_order, она берёт цены из базы,
-- считает доставку и списывает остаток. Свои действия покупатель делает тоже только через функции.

-- ---------- убираем первую схему ----------
drop table if exists public.order_items, public.orders, public.product_variants, public.products,
  public.categories, public.expenses, public.shops cascade;
drop function if exists private.owns_shop(uuid) cascade;
drop function if exists public.owns_shop(uuid) cascade;
drop function if exists public.touch_updated_at() cascade;

create schema if not exists private;
revoke all on schema private from public, anon;
grant usage on schema private to authenticated;

-- артикул: только цифры, от 100001, у каждого товара свой и не меняется
create sequence public.sku_seq start 100001;
-- номер заказа: сквозной, 1001, 1002, ...
create sequence public.order_no_seq start 1001;

-- ---------- магазины ----------
create table public.shops (
  id           uuid primary key default gen_random_uuid(),
  owner_id     uuid not null unique default auth.uid() references auth.users (id) on delete cascade,
  name         text not null check (char_length(name) between 1 and 60),
  kind         text not null check (kind in ('grocery', 'perfume', 'tech', 'food')),
  phone        text not null default '',
  city         text not null default 'Шахритус',
  address      text not null default '',
  landmark     text not null default '',
  lat          double precision check (lat is null or lat between -90 and 90),
  lng          double precision check (lng is null or lng between -180 and 180),
  about        text not null default '' check (char_length(about) <= 300),
  logo         text not null default '',
  cover        text not null default '',
  banner       text not null default '',
  paused       boolean not null default false,
  min_order    numeric(12, 2) not null default 0 check (min_order >= 0),
  prep_min     integer not null default 30 check (prep_min between 1 and 600),
  delivery     boolean not null default true,
  pickup       boolean not null default true,
  schedule     jsonb not null default '[]'::jsonb,
  cats         text[] not null default '{}',
  rating       numeric(2, 1) not null default 0,
  rating_count integer not null default 0,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
-- закрытое: Alif, сотрудники, мелодия и прочие настройки кабинета
create table public.shop_private (
  shop_id    uuid primary key references public.shops (id) on delete cascade,
  data       jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- владелец ли текущий пользователь этого магазина — для политик доступа
create function private.owns_shop(p_shop uuid)
returns boolean language sql stable security definer set search_path = ''
as $$ select exists (select 1 from public.shops s where s.id = p_shop and s.owner_id = (select auth.uid())); $$;
revoke execute on function private.owns_shop(uuid) from public, anon;
grant execute on function private.owns_shop(uuid) to authenticated;

-- ---------- товары ----------
create table public.products (
  id         text primary key check (char_length(id) between 4 and 64),
  sku        bigint not null unique default nextval('public.sku_seq'),
  shop_id    uuid not null references public.shops (id) on delete cascade,
  name       text not null check (char_length(name) between 1 and 80),
  cat        text not null default '',
  price      numeric(12, 2) not null check (price > 0),
  old_price  numeric(12, 2) check (old_price is null or old_price > 0),
  unit       text not null default 'шт',
  stock      numeric(12, 3) not null default 0 check (stock >= 0),
  active     boolean not null default true,
  stop_until timestamptz,
  expiry     date,
  -- фото, описание, варианты (без закупки), добавки, характеристики, метки, шаг веса
  data       jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter sequence public.sku_seq owned by public.products.sku;
-- закупочные цены видит только владелец
create table public.product_private (
  product_id    text primary key references public.products (id) on delete cascade,
  shop_id       uuid not null references public.shops (id) on delete cascade,
  cost          numeric(12, 2) check (cost is null or cost >= 0),
  variant_costs jsonb not null default '{}'::jsonb
);

-- ---------- заказы ----------
create table public.orders (
  id            text primary key default gen_random_uuid()::text check (char_length(id) between 4 and 64),
  no            bigint not null unique default nextval('public.order_no_seq'),
  shop_id       uuid not null references public.shops (id) on delete cascade,
  buyer_id      uuid references auth.users (id) on delete set null,
  source        text not null check (source in ('app', 'shop')),
  status        text not null default 'new' check (status in ('new', 'accepted', 'ready', 'done', 'cancelled')),
  delivery      text not null default 'courier' check (delivery in ('courier', 'pickup', 'shop')),
  -- строки заказа: артикул, название, цена на момент заказа; сборщик дописывает вес, «нет в наличии», замену
  items         jsonb not null check (jsonb_typeof(items) = 'array'),
  sum           numeric(12, 2) not null default 0,
  fee           numeric(12, 2) not null default 0,
  total         numeric(12, 2) not null default 0,
  km            numeric(8, 1),
  pay           text not null default 'cash',
  customer      jsonb not null default '{}'::jsonb,
  comment       text not null default '' check (char_length(comment) <= 600),
  if_missing    text not null default 'replace' check (if_missing in ('call', 'replace', 'remove')),
  when_at       timestamptz,
  when_label    text,
  ready_in      integer,
  cancel_reason text not null default '',
  problem       jsonb,
  created_at    timestamptz not null default now(),
  accepted_at   timestamptz,
  received_at   timestamptz,
  updated_at    timestamptz not null default now()
);
alter sequence public.order_no_seq owned by public.orders.no;
-- закупочные цены строк заказа — для прибыли в статистике, видит только магазин
create table public.order_private (
  order_id text primary key references public.orders (id) on delete cascade,
  shop_id  uuid not null references public.shops (id) on delete cascade,
  costs    jsonb not null default '[]'::jsonb
);

-- ---------- отзывы ----------
create table public.reviews (
  id         uuid primary key default gen_random_uuid(),
  order_id   text not null unique references public.orders (id) on delete cascade,
  shop_id    uuid not null references public.shops (id) on delete cascade,
  buyer_id   uuid references auth.users (id) on delete set null,
  order_no   bigint not null,
  name       text not null default 'Покупатель',
  rating     smallint not null check (rating between 1 and 5),
  tags       text[] not null default '{}',
  text       text not null default '' check (char_length(text) <= 1000),
  items      jsonb not null default '[]'::jsonb,
  reply      text,
  reply_at   timestamptz,
  complaint  jsonb,
  created_at timestamptz not null default now()
);

-- ---------- расходы ----------
create table public.expenses (
  id             text primary key check (char_length(id) between 4 and 64),
  shop_id        uuid not null references public.shops (id) on delete cascade,
  spent_on       date not null default current_date,
  cat            text not null,
  amount         numeric(12, 2) not null check (amount > 0),
  note           text not null default '',
  stock_purchase boolean not null default false,
  created_at     timestamptz not null default now()
);

-- ---------- индексы ----------
create index products_shop_idx   on public.products (shop_id);
create index product_private_shop_idx on public.product_private (shop_id);
create index orders_shop_idx     on public.orders (shop_id, created_at desc);
create index orders_buyer_idx    on public.orders (buyer_id, created_at desc);
create index order_private_shop_idx on public.order_private (shop_id);
create index reviews_shop_idx    on public.reviews (shop_id, created_at desc);
create index reviews_buyer_idx   on public.reviews (buyer_id);
create index expenses_shop_idx   on public.expenses (shop_id, spent_on desc);

-- ---------- служебные триггеры ----------
create function private.touch() returns trigger language plpgsql set search_path = ''
as $$ begin new.updated_at := now(); return new; end; $$;
create trigger shops_touch    before update on public.shops    for each row execute function private.touch();
create trigger products_touch before update on public.products for each row execute function private.touch();
create trigger orders_touch   before update on public.orders   for each row execute function private.touch();

-- магазин не может переписать, чей это заказ, его номер и сумму оплаты покупателя
create function private.guard_order() returns trigger language plpgsql set search_path = ''
as $$
begin
  if new.shop_id <> old.shop_id or new.buyer_id is distinct from old.buyer_id or new.no <> old.no
     or new.source <> old.source or new.created_at <> old.created_at then
    raise exception 'Нельзя менять магазин, покупателя, номер и время заказа';
  end if;
  return new;
end;
$$;
create trigger orders_guard before update on public.orders for each row execute function private.guard_order();

-- рейтинг магазина: средняя оценка за 3 месяца без скрытых модератором отзывов
create function private.recount_rating() returns trigger language plpgsql security definer set search_path = ''
as $$
declare v_shop uuid := coalesce(new.shop_id, old.shop_id);
begin
  update public.shops s set
    rating = coalesce((select round(avg(r.rating)::numeric, 1) from public.reviews r
                       where r.shop_id = v_shop and r.created_at > now() - interval '90 days' and coalesce((r.complaint ->> 'hidden')::boolean, false) = false), 0),
    rating_count = (select count(*) from public.reviews r where r.shop_id = v_shop and r.created_at > now() - interval '90 days')
  where s.id = v_shop;
  return null;
end;
$$;
create trigger reviews_rating after insert or update or delete on public.reviews for each row execute function private.recount_rating();

-- ---------- доставка: тот же расчёт, что в приложении (client/js/model/delivery.js) ----------
-- зона: 15 км вокруг посёлка Тус (Шахритус); цена: до 2 км — 15, до 5 км — 20, дальше 20 + 2 за км
create function private.km_between(a_lat double precision, a_lng double precision, b_lat double precision, b_lng double precision)
returns double precision language sql immutable set search_path = ''
as $$
  select 2 * 6371 * asin(sqrt(
    power(sin(radians(b_lat - a_lat) / 2), 2) + cos(radians(a_lat)) * cos(radians(b_lat)) * power(sin(radians(b_lng - a_lng) / 2), 2)));
$$;
create function private.delivery_quote(s_lat double precision, s_lng double precision, a_lat double precision, a_lng double precision)
returns table (km numeric, fee numeric, ok boolean) language plpgsql immutable set search_path = ''
as $$
declare
  c_lat constant double precision := 37.267; c_lng constant double precision := 68.133;
  f_lat double precision := coalesce(s_lat, c_lat); f_lng double precision := coalesce(s_lng, c_lng);
  t_lat double precision := coalesce(a_lat, c_lat); t_lng double precision := coalesce(a_lng, c_lng);
  d numeric;
begin
  d := greatest(0.3, round((private.km_between(f_lat, f_lng, t_lat, t_lng) * 1.3)::numeric, 1));
  km := d;
  fee := case when d <= 2 then 15 when d <= 5 then 20 else 20 + ceil(d - 5) * 2 end;
  ok := d <= 30 and (a_lat is null or private.km_between(c_lat, c_lng, a_lat, a_lng) <= 15);
  return next;
end;
$$;

-- ---------- заказ покупателя ----------
-- p_items: [{ "pid": "...", "vid": "...", "opts": ["..."], "qty": 1.5 }]
-- p_addr:  { "city", "street", "house", "entrance", "floor", "apt", "intercom", "landmark", "lat", "lng" }
create function public.place_order(
  p_shop uuid, p_items jsonb, p_addr jsonb, p_name text, p_phone text,
  p_pay text default 'cash', p_comment text default '', p_if_missing text default 'replace',
  p_when_at timestamptz default null, p_when_label text default null
) returns public.orders
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_shop public.shops;
  v_line jsonb; v_prod public.products; v_var jsonb; v_opt jsonb;
  v_items jsonb := '[]'::jsonb; v_costs jsonb := '[]'::jsonb;
  v_price numeric; v_qty numeric; v_sum numeric := 0; v_opts jsonb; v_cost numeric;
  v_q record; v_order public.orders; v_addr text;
begin
  if v_uid is null then raise exception 'Нужно войти'; end if;
  select * into v_shop from public.shops where id = p_shop;
  if not found then raise exception 'Магазин не найден'; end if;
  if v_shop.paused then raise exception 'Магазин сейчас не принимает заказы'; end if;
  if jsonb_typeof(p_items) <> 'array' or jsonb_array_length(p_items) = 0 or jsonb_array_length(p_items) > 60 then raise exception 'Корзина пустая'; end if;
  if p_pay not in ('card', 'cash') then raise exception 'Неизвестный способ оплаты'; end if;
  if char_length(coalesce(p_phone, '')) < 9 then raise exception 'Нужен номер телефона'; end if;

  for v_line in select * from jsonb_array_elements(p_items) loop
    select * into v_prod from public.products where id = v_line ->> 'pid' and shop_id = p_shop for update;
    if not found or not v_prod.active or (v_prod.stop_until is not null and v_prod.stop_until > now())
       or (v_prod.expiry is not null and v_prod.expiry < current_date) then
      raise exception 'Товара больше нет в продаже: %', coalesce(v_prod.name, v_line ->> 'pid');
    end if;
    v_qty := (v_line ->> 'qty')::numeric;
    if v_qty is null or v_qty <= 0 then raise exception 'Неверное количество'; end if;
    if v_qty > v_prod.stock then raise exception 'Осталось только % % «%»', v_prod.stock, v_prod.unit, v_prod.name; end if;
    v_price := v_prod.price; v_var := null;
    if coalesce(v_line ->> 'vid', '') <> '' then
      select e into v_var from jsonb_array_elements(coalesce(v_prod.data -> 'variants', '[]'::jsonb)) e where e ->> 'id' = v_line ->> 'vid';
      if v_var is null then raise exception 'Вариант товара «%» больше недоступен', v_prod.name; end if;
      v_price := (v_var ->> 'price')::numeric;
    end if;
    v_opts := '[]'::jsonb;
    for v_opt in select e from jsonb_array_elements(coalesce(v_prod.data -> 'options', '[]'::jsonb)) e
                 where e ->> 'id' in (select jsonb_array_elements_text(coalesce(v_line -> 'opts', '[]'::jsonb))) loop
      v_price := v_price + coalesce((v_opt ->> 'price')::numeric, 0);
      v_opts := v_opts || jsonb_build_object('name', v_opt ->> 'name', 'price', coalesce((v_opt ->> 'price')::numeric, 0));
    end loop;
    v_sum := v_sum + round(v_price * v_qty, 2);
    v_items := v_items || jsonb_build_object('pid', v_prod.id, 'sku', v_prod.sku, 'name', v_prod.name, 'unit', v_prod.unit,
      'variant', coalesce(v_var ->> 'name', ''), 'qty', v_qty, 'price', v_price, 'opts', v_opts);
    select case when v_var is not null then (pp.variant_costs ->> (v_var ->> 'id'))::numeric else pp.cost end into v_cost
      from public.product_private pp where pp.product_id = v_prod.id;
    v_costs := v_costs || to_jsonb(v_cost);
    update public.products set stock = stock - v_qty where id = v_prod.id;
  end loop;

  if v_sum < v_shop.min_order then raise exception 'Минимальный заказ — % смн', v_shop.min_order; end if;
  select * into v_q from private.delivery_quote(v_shop.lat, v_shop.lng, (p_addr ->> 'lat')::double precision, (p_addr ->> 'lng')::double precision);
  if not v_q.ok then raise exception 'Этот адрес вне зоны доставки'; end if;

  v_addr := concat_ws(', ', nullif(p_addr ->> 'city', ''), nullif(p_addr ->> 'street', ''), 'д. ' || nullif(p_addr ->> 'house', ''),
    'кв. ' || nullif(p_addr ->> 'apt', ''), 'подъезд ' || nullif(p_addr ->> 'entrance', ''), 'этаж ' || nullif(p_addr ->> 'floor', ''),
    'домофон ' || nullif(p_addr ->> 'intercom', ''), 'ориентир: ' || nullif(p_addr ->> 'landmark', ''));
  insert into public.orders (shop_id, buyer_id, source, delivery, items, sum, fee, total, km, pay, customer, comment, if_missing, when_at, when_label)
  values (p_shop, v_uid, 'app', 'courier', v_items, v_sum, v_q.fee, v_sum + v_q.fee, v_q.km, p_pay,
          jsonb_build_object('name', left(coalesce(nullif(trim(p_name), ''), 'Покупатель'), 40), 'phone', left(p_phone, 20), 'address', v_addr, 'addr', p_addr),
          left(coalesce(p_comment, ''), 600), coalesce(nullif(p_if_missing, ''), 'replace'), p_when_at, p_when_label)
  returning * into v_order;
  insert into public.order_private (order_id, shop_id, costs) values (v_order.id, p_shop, v_costs);
  return v_order;
end;
$$;

-- покупатель: ответить на замену, отменить новый заказ, отметить получение, сообщить о проблеме, оставить отзыв
create function public.buyer_answer_sub(p_order text, p_n integer, p_yes boolean)
returns void language plpgsql security definer set search_path = ''
as $$
declare v public.orders;
begin
  select * into v from public.orders where id = p_order and buyer_id = auth.uid() for update;
  if not found then raise exception 'Заказ не найден'; end if;
  if v.items -> p_n -> 'sub' ->> 'status' <> 'wait' then return; end if;
  update public.orders set items = jsonb_set(jsonb_set(items, array[p_n::text, 'sub', 'status'], to_jsonb(case when p_yes then 'ok' else 'no' end)),
    array[p_n::text, 'picked'], 'false'::jsonb) where id = p_order;
end;
$$;
create function public.buyer_cancel(p_order text)
returns void language plpgsql security definer set search_path = ''
as $$
declare v public.orders; i jsonb;
begin
  select * into v from public.orders where id = p_order and buyer_id = auth.uid() for update;
  if not found then raise exception 'Заказ не найден'; end if;
  if v.status <> 'new' then raise exception 'Магазин уже собирает заказ — отменить нельзя'; end if;
  for i in select * from jsonb_array_elements(v.items) loop
    update public.products set stock = stock + (i ->> 'qty')::numeric where id = i ->> 'pid';
  end loop;
  update public.orders set status = 'cancelled', cancel_reason = 'Покупатель отменил заказ' where id = p_order;
end;
$$;
create function public.buyer_received(p_order text)
returns void language plpgsql security definer set search_path = ''
as $$
begin
  update public.orders set received_at = coalesce(received_at, now())
  where id = p_order and buyer_id = auth.uid() and status in ('ready', 'done');
  if not found then raise exception 'Заказ ещё не передан курьеру'; end if;
end;
$$;
create function public.buyer_problem(p_order text, p_reason text, p_text text default '')
returns void language plpgsql security definer set search_path = ''
as $$
begin
  update public.orders set problem = jsonb_build_object('reason', left(p_reason, 100), 'text', left(coalesce(p_text, ''), 600), 'ts', now())
  where id = p_order and buyer_id = auth.uid();
  if not found then raise exception 'Заказ не найден'; end if;
end;
$$;
create function public.buyer_review(p_order text, p_rating integer, p_tags text[], p_text text, p_likes jsonb, p_name text)
returns void language plpgsql security definer set search_path = ''
as $$
declare v public.orders;
begin
  select * into v from public.orders where id = p_order and buyer_id = auth.uid();
  if not found then raise exception 'Заказ не найден'; end if;
  if v.received_at is null then raise exception 'Оценить можно после получения заказа'; end if;
  insert into public.reviews (order_id, shop_id, buyer_id, order_no, name, rating, tags, text, items)
  values (v.id, v.shop_id, v.buyer_id, v.no, left(coalesce(nullif(trim(p_name), ''), 'Покупатель'), 40), p_rating, coalesce(p_tags, '{}'),
          left(coalesce(p_text, ''), 1000),
          coalesce((select jsonb_agg(jsonb_build_object('pid', i ->> 'pid', 'name', i ->> 'name', 'like', p_likes -> (i ->> 'pid')))
                    from jsonb_array_elements(v.items) i), '[]'::jsonb))
  on conflict (order_id) do nothing;
end;
$$;
revoke execute on function public.place_order(uuid, jsonb, jsonb, text, text, text, text, text, timestamptz, text) from public, anon;
revoke execute on function public.buyer_answer_sub(text, integer, boolean) from public, anon;
revoke execute on function public.buyer_cancel(text) from public, anon;
revoke execute on function public.buyer_received(text) from public, anon;
revoke execute on function public.buyer_problem(text, text, text) from public, anon;
revoke execute on function public.buyer_review(text, integer, text[], text, jsonb, text) from public, anon;
grant execute on function public.place_order(uuid, jsonb, jsonb, text, text, text, text, text, timestamptz, text) to authenticated;
grant execute on function public.buyer_answer_sub(text, integer, boolean) to authenticated;
grant execute on function public.buyer_cancel(text) to authenticated;
grant execute on function public.buyer_received(text) to authenticated;
grant execute on function public.buyer_problem(text, text, text) to authenticated;
grant execute on function public.buyer_review(text, integer, text[], text, jsonb, text) to authenticated;
revoke execute on function private.km_between(double precision, double precision, double precision, double precision) from public, anon;
revoke execute on function private.delivery_quote(double precision, double precision, double precision, double precision) from public, anon;

-- ---------- доступ к строкам ----------
alter table public.shops           enable row level security;
alter table public.shop_private    enable row level security;
alter table public.products        enable row level security;
alter table public.product_private enable row level security;
alter table public.orders          enable row level security;
alter table public.order_private   enable row level security;
alter table public.reviews         enable row level security;
alter table public.expenses        enable row level security;

-- витрина открыта всем
create policy shops_read on public.shops for select to anon, authenticated using (true);
create policy shops_insert on public.shops for insert to authenticated with check (owner_id = (select auth.uid()));
create policy shops_update on public.shops for update to authenticated using (owner_id = (select auth.uid())) with check (owner_id = (select auth.uid()));
create policy shops_delete on public.shops for delete to authenticated using (owner_id = (select auth.uid()));

create policy shop_private_owner on public.shop_private for all to authenticated
  using ((select private.owns_shop(shop_id))) with check ((select private.owns_shop(shop_id)));

create policy products_read on public.products for select to anon, authenticated using (active or (select private.owns_shop(shop_id)));
create policy products_insert on public.products for insert to authenticated with check ((select private.owns_shop(shop_id)));
create policy products_update on public.products for update to authenticated using ((select private.owns_shop(shop_id))) with check ((select private.owns_shop(shop_id)));
create policy products_delete on public.products for delete to authenticated using ((select private.owns_shop(shop_id)));

create policy product_private_owner on public.product_private for all to authenticated
  using ((select private.owns_shop(shop_id))) with check ((select private.owns_shop(shop_id)));

create policy orders_read on public.orders for select to authenticated
  using (buyer_id = (select auth.uid()) or (select private.owns_shop(shop_id)));
-- продажи в магазине вносит сам магазин; заказы из приложения — только через place_order
create policy orders_insert on public.orders for insert to authenticated
  with check (source = 'shop' and buyer_id is null and (select private.owns_shop(shop_id)));
create policy orders_update on public.orders for update to authenticated
  using ((select private.owns_shop(shop_id))) with check ((select private.owns_shop(shop_id)));

create policy order_private_owner on public.order_private for all to authenticated
  using ((select private.owns_shop(shop_id))) with check ((select private.owns_shop(shop_id)));

create policy reviews_read on public.reviews for select to anon, authenticated
  using (coalesce((complaint ->> 'hidden')::boolean, false) = false or (select private.owns_shop(shop_id)));
create policy reviews_update on public.reviews for update to authenticated
  using ((select private.owns_shop(shop_id))) with check ((select private.owns_shop(shop_id)));

create policy expenses_owner on public.expenses for all to authenticated
  using ((select private.owns_shop(shop_id))) with check ((select private.owns_shop(shop_id)));

-- ---------- живые обновления: новые заказы у продавца, статус у покупателя, остатки у всех ----------
alter publication supabase_realtime add table public.orders, public.products, public.shops, public.reviews;

-- ---------- фото: папка магазина, читать могут все ----------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('media', 'media', true, 2097152, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update set public = true, file_size_limit = 2097152, allowed_mime_types = array['image/jpeg', 'image/png', 'image/webp'];
create policy media_owner_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'media' and (select private.owns_shop(((storage.foldername(name))[1])::uuid)));
create policy media_owner_update on storage.objects for update to authenticated
  using (bucket_id = 'media' and (select private.owns_shop(((storage.foldername(name))[1])::uuid)));
create policy media_owner_delete on storage.objects for delete to authenticated
  using (bucket_id = 'media' and (select private.owns_shop(((storage.foldername(name))[1])::uuid)));
