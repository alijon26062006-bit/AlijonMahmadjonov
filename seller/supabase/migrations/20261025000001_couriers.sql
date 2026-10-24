-- Курьеры: анкета, смена «на линии», лента свободных заказов, доставка по шагам с кодом получения.
--
-- Кто что видит:
--   * курьер — свою анкету и свои заказы (после «Беру»: адрес и телефон покупателя);
--     свободные заказы — только через courier_feed, без телефона и точного адреса покупателя;
--   * покупатель и магазин — кто везёт заказ (снимок анкеты в orders.courier) и где курьер сейчас;
--   * код получения знает только покупатель: курьер вводит его у двери, иначе отметить «Доставил» нельзя.
-- Все изменения курьера — только через функции ниже; напрямую писать в эти поля не может никто.

-- ---------- настройки сервиса ----------
-- доля платы за доставку, которая достаётся курьеру (1 — вся). Поменять: create or replace ... select 0.9
create function private.courier_share() returns numeric language sql immutable set search_path = '' as $$ select 1.0 $$;
-- как далеко от курьера показывать свободные заказы, км по прямой
create function private.courier_radius() returns double precision language sql immutable set search_path = '' as $$ select 15.0 $$;

-- ---------- анкета курьера ----------
create table public.couriers (
  id           uuid primary key default auth.uid() references auth.users (id) on delete cascade,
  name         text not null check (char_length(name) between 1 and 40),
  phone        text not null check (char_length(phone) between 9 and 20),
  car          text not null default '' check (char_length(car) <= 40),     -- марка и цвет: «Opel Astra, белый»
  plate        text not null default '' check (char_length(plate) <= 15),
  photo        text not null default '',
  status       text not null default 'active' check (status in ('active', 'blocked')),  -- для теста допускаем сразу
  online       boolean not null default false,
  lat          double precision check (lat is null or lat between -90 and 90),
  lng          double precision check (lng is null or lng between -180 and 180),
  loc_at       timestamptz,
  rating       numeric(2, 1) not null default 0,
  rating_count integer not null default 0,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create trigger couriers_touch before update on public.couriers for each row execute function private.touch();
alter table public.couriers enable row level security;
-- писать в анкету напрямую нельзя: правило есть только на чтение своей строки, всё остальное — через функции ниже
create policy couriers_self on public.couriers for select to authenticated using (id = (select auth.uid()));

-- ---------- курьер в заказе ----------
alter table public.orders
  add column courier_id     uuid references public.couriers (id) on delete set null,
  add column courier        jsonb,          -- снимок анкеты: имя, телефон, машина, номер — для покупателя и магазина
  add column courier_status text check (courier_status in ('going', 'at_shop', 'picked', 'at_client', 'delivered', 'returned')),
  add column courier_at     timestamptz,    -- когда взял заказ
  add column picked_at      timestamptz,
  add column delivered_at   timestamptz,
  add column courier_fee    numeric(12, 2), -- сколько заработал курьер
  add column cash_taken     numeric(12, 2), -- сколько наличных взял у покупателя
  add column courier_rating smallint check (courier_rating between 1 and 5);
create index orders_courier_idx on public.orders (courier_id, created_at desc);
create index orders_free_idx on public.orders (created_at desc) where courier_id is null and source = 'app';

create policy orders_read_courier on public.orders for select to authenticated using (courier_id = (select auth.uid()));

-- код получения: 4 цифры, видит только покупатель
create table private.order_codes (
  order_id text primary key references public.orders (id) on delete cascade,
  code     text not null check (code ~ '^\d{4}$')
);

-- поля курьера меняют только функции курьера/покупателя (они ставят метку zud.trusted)
create or replace function private.guard_order() returns trigger language plpgsql set search_path = ''
as $$
begin
  if new.shop_id <> old.shop_id or new.buyer_id is distinct from old.buyer_id or new.no <> old.no
     or new.source <> old.source or new.created_at <> old.created_at then
    raise exception 'Нельзя менять магазин, покупателя, номер и время заказа';
  end if;
  if coalesce(current_setting('zud.trusted', true), '') <> '1' and (
       new.courier_id is distinct from old.courier_id or new.courier is distinct from old.courier
    or new.courier_status is distinct from old.courier_status or new.courier_at is distinct from old.courier_at
    or new.picked_at is distinct from old.picked_at or new.delivered_at is distinct from old.delivered_at
    or new.courier_fee is distinct from old.courier_fee or new.cash_taken is distinct from old.cash_taken
    or new.courier_rating is distinct from old.courier_rating) then
    raise exception 'Данные курьера в заказе меняются только из приложения курьера';
  end if;
  return new;
end;
$$;
create function private.trust() returns void language sql set search_path = ''
as $$ select set_config('zud.trusted', '1', true); $$;

-- ---------- что видит курьер ----------
-- заказ целиком: магазин, покупатель, состав, деньги, этап
create function private.job(o public.orders) returns jsonb language sql stable set search_path = ''
as $$
  select jsonb_build_object(
    'id', o.id, 'no', o.no, 'status', o.status, 'step', o.courier_status, 'created_at', o.created_at, 'taken_at', o.courier_at,
    'picked_at', o.picked_at, 'delivered_at', o.delivered_at, 'received_at', o.received_at,
    'ready_at', case when o.status in ('ready', 'done') then null
                     else coalesce(o.accepted_at, o.created_at) + make_interval(mins => coalesce(o.ready_in, s.prep_min)) end,
    'earn', o.courier_fee, 'pay', o.pay, 'total', o.total, 'sum', o.sum, 'fee', o.fee, 'km', o.km, 'cash_taken', o.cash_taken,
    'items', (select coalesce(jsonb_agg(jsonb_build_object('name', i ->> 'name', 'qty', i -> 'qty', 'actual', i -> 'actual', 'unit', i ->> 'unit',
                'variant', i ->> 'variant', 'missing', i -> 'missing', 'sub', i -> 'sub')), '[]'::jsonb) from jsonb_array_elements(o.items) i),
    'comment', o.comment, 'if_missing', o.if_missing, 'when_label', o.when_label, 'cancel_reason', o.cancel_reason, 'rating', o.courier_rating,
    'shop', jsonb_build_object('name', s.name, 'phone', s.phone, 'address', s.address, 'landmark', s.landmark, 'lat', s.lat, 'lng', s.lng),
    'client', jsonb_build_object('name', o.customer ->> 'name', 'phone', o.customer ->> 'phone', 'address', o.customer ->> 'address',
                'lat', o.customer -> 'addr' -> 'lat', 'lng', o.customer -> 'addr' -> 'lng'))
  from public.shops s where s.id = o.shop_id;
$$;

create function private.me() returns public.couriers language plpgsql stable set search_path = ''
as $$
declare v public.couriers;
begin
  if auth.uid() is null then raise exception 'Нужно войти'; end if;
  select * into v from public.couriers where id = auth.uid();
  if not found then raise exception 'Сначала заполните анкету курьера'; end if;
  if v.status <> 'active' then raise exception 'Доступ курьера приостановлен. Свяжитесь с поддержкой'; end if;
  return v;
end;
$$;

-- ---------- функции курьера ----------
/** Анкета: создать или изменить. */
create function public.courier_register(p_name text, p_phone text, p_car text, p_plate text, p_photo text default '')
returns public.couriers language plpgsql security definer set search_path = ''
as $$
declare v public.couriers;
begin
  if auth.uid() is null then raise exception 'Нужно войти'; end if;
  insert into public.couriers (id, name, phone, car, plate, photo)
  values (auth.uid(), left(trim(p_name), 40), left(trim(p_phone), 20), left(trim(coalesce(p_car, '')), 40), upper(left(trim(coalesce(p_plate, '')), 15)), coalesce(p_photo, ''))
  on conflict (id) do update set name = excluded.name, phone = excluded.phone, car = excluded.car, plate = excluded.plate, photo = excluded.photo
  returning * into v;
  return v;
end;
$$;

/** На линии / не на линии. Место — если телефон его знает. */
create function public.courier_online(p_on boolean, p_lat double precision default null, p_lng double precision default null)
returns public.couriers language plpgsql security definer set search_path = ''
as $$
declare v public.couriers;
begin
  perform private.me();
  update public.couriers set online = p_on, lat = coalesce(p_lat, lat), lng = coalesce(p_lng, lng), loc_at = case when p_lat is null then loc_at else now() end
  where id = auth.uid() returning * into v;
  return v;
end;
$$;

/** Где курьер сейчас: телефон присылает раз в 10–15 секунд, пока курьер на линии. */
create function public.courier_ping(p_lat double precision, p_lng double precision)
returns void language sql security definer set search_path = ''
as $$ update public.couriers set lat = p_lat, lng = p_lng, loc_at = now() where id = auth.uid(); $$;

/** Свободные заказы рядом: магазин уже принял заказ (собирает или собрал), курьера ещё нет. Ближние — первыми. */
create function public.courier_feed()
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare me public.couriers := private.me();
begin
  return coalesce((
    select jsonb_agg(t.x order by (t.x ->> 'to_shop')::numeric nulls last, t.x ->> 'created_at')
    from (
      select jsonb_build_object(
        'id', o.id, 'no', o.no, 'status', o.status, 'created_at', o.created_at,
        'shop', s.name, 'shop_address', s.address, 'shop_lat', s.lat, 'shop_lng', s.lng,
        'to_shop', case when me.lat is null or s.lat is null then null
                        else greatest(0.1, round((private.km_between(me.lat, me.lng, s.lat, s.lng) * 1.3)::numeric, 1)) end,
        'km', o.km, 'earn', round(o.fee * private.courier_share(), 2), 'pay', o.pay,
        'cash', case when o.pay = 'cash' then o.total end, 'items', jsonb_array_length(o.items),
        'ready_at', case when o.status = 'ready' then null
                         else coalesce(o.accepted_at, o.created_at) + make_interval(mins => coalesce(o.ready_in, s.prep_min)) end,
        'area', concat_ws(', ', nullif(o.customer -> 'addr' ->> 'city', ''), nullif(o.customer -> 'addr' ->> 'street', '')),
        'to_lat', o.customer -> 'addr' -> 'lat', 'to_lng', o.customer -> 'addr' -> 'lng') as x
      from public.orders o join public.shops s on s.id = o.shop_id
      where o.source = 'app' and o.delivery = 'courier' and o.courier_id is null and o.status in ('accepted', 'ready')
        and o.created_at > now() - interval '1 day'
        and (me.lat is null or s.lat is null or private.km_between(me.lat, me.lng, s.lat, s.lng) <= private.courier_radius())
      order by o.created_at
      limit 40
    ) t), '[]'::jsonb);
end;
$$;

/** «Беру»: заказ достаётся одному курьеру — кто первым нажал. */
create function public.courier_take(p_order text)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare me public.couriers := private.me(); v public.orders;
begin
  perform private.trust();
  if exists (select 1 from public.orders where courier_id = me.id and courier_status in ('going', 'at_shop', 'picked', 'at_client') and status <> 'cancelled') then
    raise exception 'Сначала доставьте текущий заказ';
  end if;
  update public.orders set courier_id = me.id, courier_status = 'going', courier_at = now(), courier_fee = round(fee * private.courier_share(), 2),
    courier = jsonb_build_object('name', me.name, 'phone', me.phone, 'car', me.car, 'plate', me.plate, 'photo', me.photo, 'rating', me.rating, 'rating_count', me.rating_count)
  where id = p_order and courier_id is null and source = 'app' and delivery = 'courier' and status in ('accepted', 'ready')
  returning * into v;
  if not found then raise exception 'Этот заказ уже взял другой курьер'; end if;
  insert into private.order_codes (order_id, code) values (v.id, lpad(floor(random() * 10000)::int::text, 4, '0'))
  on conflict (order_id) do update set code = excluded.code;
  return private.job(v);
end;
$$;

/** Мои заказы: текущие и доставленные за p_days дней (для заработка). */
create function public.courier_jobs(p_days integer default 0)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare me public.couriers := private.me();
begin
  return coalesce((select jsonb_agg(private.job(o) order by o.courier_at desc) from public.orders o
    where o.courier_id = me.id and (o.courier_status in ('going', 'at_shop', 'picked', 'at_client')
       or o.courier_at > now() - make_interval(days => greatest(p_days, 0)) or (o.courier_at > now() - interval '12 hours'))), '[]'::jsonb);
end;
$$;

/** Шаг доставки: at_shop → picked → at_client → delivered (с кодом покупателя). */
create function public.courier_step(p_order text, p_step text, p_code text default null)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare me public.couriers := private.me(); v public.orders; v_code text;
begin
  perform private.trust();
  select * into v from public.orders where id = p_order and courier_id = me.id for update;
  if not found then raise exception 'Заказ не найден'; end if;
  if v.status = 'cancelled' then raise exception 'Заказ отменён: %', coalesce(nullif(v.cancel_reason, ''), 'без причины'); end if;
  if p_step = 'at_shop' then
    if v.courier_status = 'going' then update public.orders set courier_status = 'at_shop' where id = v.id returning * into v; end if;
  elsif p_step = 'picked' then
    if v.courier_status not in ('going', 'at_shop') then raise exception 'Заказ уже забран'; end if;
    update public.orders set courier_status = 'picked', picked_at = now(), status = 'done' where id = v.id returning * into v;
  elsif p_step = 'at_client' then
    if v.courier_status = 'picked' then update public.orders set courier_status = 'at_client' where id = v.id returning * into v; end if;
  elsif p_step = 'delivered' then
    if v.courier_status not in ('picked', 'at_client') then raise exception 'Сначала заберите заказ в магазине'; end if;
    select code into v_code from private.order_codes where order_id = v.id;
    if p_code is distinct from v_code then raise exception 'Код не подходит. Спросите у покупателя 4 цифры из его приложения'; end if;
    update public.orders set courier_status = 'delivered', delivered_at = now(), received_at = coalesce(received_at, now()),
      cash_taken = case when pay = 'cash' then total end
    where id = v.id returning * into v;
  else
    raise exception 'Неизвестный шаг: %', p_step;
  end if;
  return private.job(v);
end;
$$;

/** Отказаться от заказа, пока не забрал: заказ снова свободен для других курьеров. */
create function public.courier_release(p_order text)
returns void language plpgsql security definer set search_path = ''
as $$
declare me public.couriers := private.me();
begin
  perform private.trust();
  update public.orders set courier_id = null, courier = null, courier_status = null, courier_at = null, courier_fee = null
  where id = p_order and courier_id = me.id and courier_status in ('going', 'at_shop');
  if not found then raise exception 'Заказ уже забран — отказаться нельзя. Если не получается доставить, нажмите «Не могу передать»'; end if;
  -- старый код не трогаем: следующий курьер при «Беру» получит новый (courier_take перезаписывает)
end;
$$;

/** Не получилось передать (покупатель не отвечает): заказ возвращается в магазин, поддержка видит проблему. */
create function public.courier_return(p_order text, p_reason text)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare me public.couriers := private.me(); v public.orders;
begin
  perform private.trust();
  update public.orders set courier_status = 'returned',
    problem = jsonb_build_object('reason', 'Курьер не смог передать заказ', 'text', left(coalesce(p_reason, ''), 300), 'ts', now(), 'by', 'courier')
  where id = p_order and courier_id = me.id and courier_status in ('picked', 'at_client') returning * into v;
  if not found then raise exception 'Заказ не найден'; end if;
  return private.job(v);
end;
$$;

-- ---------- покупатель и магазин ----------
/** Код получения для покупателя: показывает его курьеру у двери. */
create function public.buyer_code(p_order text)
returns text language sql security definer set search_path = ''
as $$
  select c.code from private.order_codes c join public.orders o on o.id = c.order_id
  where c.order_id = p_order and o.buyer_id = auth.uid() and o.courier_id is not null;
$$;

/** Где курьер: для покупателя и магазина, пока заказ в пути. */
create function public.order_courier_where(p_order text)
returns jsonb language sql security definer set search_path = ''
as $$
  select jsonb_build_object('lat', c.lat, 'lng', c.lng, 'at', c.loc_at)
  from public.orders o join public.couriers c on c.id = o.courier_id
  where o.id = p_order and (o.buyer_id = auth.uid() or private.owns_shop(o.shop_id))
    and o.courier_status in ('going', 'at_shop', 'picked', 'at_client') and c.loc_at > now() - interval '10 minutes';
$$;

/** Покупатель оценивает курьера (одна оценка на заказ). */
create function public.buyer_rate_courier(p_order text, p_rating integer)
returns void language plpgsql security definer set search_path = ''
as $$
declare v public.orders;
begin
  perform private.trust();
  update public.orders set courier_rating = greatest(1, least(5, p_rating))
  where id = p_order and buyer_id = auth.uid() and courier_id is not null and courier_rating is null
    and (courier_status = 'delivered' or received_at is not null)
  returning * into v;
  if not found then return; end if;
  update public.couriers c set (rating, rating_count) = (
    select coalesce(round(avg(o.courier_rating), 1), 0), count(o.courier_rating) from public.orders o
    where o.courier_id = c.id and o.courier_rating is not null and o.delivered_at > now() - interval '90 days')
  where c.id = v.courier_id;
end;
$$;

-- покупатель нажал «Получил» сам — курьерская доставка тоже закрывается
create or replace function public.buyer_received(p_order text)
returns void language plpgsql security definer set search_path = ''
as $$
begin
  perform private.trust();
  update public.orders set received_at = coalesce(received_at, now()),
    courier_status = case when courier_id is not null then 'delivered' else courier_status end,
    delivered_at = case when courier_id is not null then coalesce(delivered_at, now()) else delivered_at end,
    cash_taken = case when courier_id is not null and pay = 'cash' then coalesce(cash_taken, total) else cash_taken end
  where id = p_order and buyer_id = auth.uid() and status in ('ready', 'done');
  if not found then raise exception 'Заказ ещё не передан курьеру'; end if;
end;
$$;

-- ---------- права ----------
revoke execute on function private.courier_share(), private.courier_radius(), private.trust(), private.job(public.orders), private.me() from public, anon, authenticated;
revoke execute on function public.courier_register(text, text, text, text, text), public.courier_online(boolean, double precision, double precision),
  public.courier_ping(double precision, double precision), public.courier_feed(), public.courier_take(text), public.courier_jobs(integer),
  public.courier_step(text, text, text), public.courier_release(text), public.courier_return(text, text),
  public.buyer_code(text), public.order_courier_where(text), public.buyer_rate_courier(text, integer) from public, anon;
grant execute on function public.courier_register(text, text, text, text, text), public.courier_online(boolean, double precision, double precision),
  public.courier_ping(double precision, double precision), public.courier_feed(), public.courier_take(text), public.courier_jobs(integer),
  public.courier_step(text, text, text), public.courier_release(text), public.courier_return(text, text),
  public.buyer_code(text), public.order_courier_where(text), public.buyer_rate_courier(text, integer) to authenticated;

