-- Админ-панель «Зуд»: один человек видит всё и всех — людей, роли, магазины, товары, заказы, курьеров, отзывы — и как они связаны.
--
-- Роли (один номер телефона = одна учётная запись, ролей у неё может быть несколько сразу):
--   * покупатель — делал заказы в приложении (orders.buyer_id);
--   * продавец   — владелец магазина (shops.owner_id);
--   * сотрудник  — его номер есть в списке сотрудников магазина (shop_private.data.staff: управляющий, кассир, сборщик);
--   * курьер     — заполнил анкету курьера (couriers.id);
--   * админ      — есть в private.admins. Входит по почте и паролю, а не по номеру: тестовый вход по номеру без SMS
--                  не годится для доступа ко всему.
--
-- Админ ничего не пишет в таблицы напрямую: читает и меняет только через функции admin_* ниже.
-- Каждая функция сначала проверяет, что вызвал админ, а каждое действие записывается в журнал private.admin_log.
-- Блокировки снимает только админ: магазин, товар, курьер и сам человек не могут разблокировать себя сами.

-- ---------- кто админ ----------
create table private.admins (
  user_id  uuid primary key references auth.users (id) on delete cascade,
  active   boolean not null default true,   -- false — права забрали (строку оставляем для истории)
  note     text not null default '',
  added_at timestamptz not null default now(),
  added_by uuid
);
-- блокировка человека целиком: не может заказывать, работать курьером, открыть магазин; его магазин скрыт от покупателей
-- active = false — блокировку сняли (строку оставляем: история видна в журнале и карточке человека)
create table private.user_blocks (
  user_id uuid primary key references auth.users (id) on delete cascade,
  active  boolean not null default true,
  reason  text not null default '',
  prev    jsonb not null default '{}'::jsonb,   -- что было до блокировки: магазин, курьер — чтобы вернуть как было
  at      timestamptz not null default now(),
  by      uuid
);
create table private.admin_log (
  id       bigint generated always as identity primary key,
  at       timestamptz not null default now(),
  admin_id uuid,
  action   text not null,
  kind     text not null,     -- user | shop | product | order | courier | review | admin
  target   text not null,
  note     text not null default '',
  data     jsonb not null default '{}'::jsonb
);
create index admin_log_at_idx on private.admin_log (at desc);
create index admin_log_target_idx on private.admin_log (kind, target, at desc);
-- таблицы схемы private не видны через API; правила без разрешений — на всякий случай закрыты для всех
alter table private.admins enable row level security;
alter table private.user_blocks enable row level security;
alter table private.admin_log enable row level security;

-- ---------- блокировка магазина и товара ----------
alter table public.shops
  add column blocked      boolean not null default false,
  add column block_reason text not null default '';
alter table public.products
  add column blocked      boolean not null default false,
  add column block_reason text not null default '';
alter table public.couriers
  add column block_reason text not null default '';

-- заблокированный магазин и его товары не видит никто, кроме владельца (и админа через функции)
alter policy shops_read on public.shops using (not blocked or owner_id = (select auth.uid()));
alter policy products_read on public.products using (active and not blocked and exists (select 1 from public.shops s where s.id = shop_id));

-- блокировку меняют только функции админа (метка zud.trusted); владелец не снимет её обычным сохранением
create function private.guard_blocked() returns trigger language plpgsql set search_path = ''
as $$
begin
  if coalesce(current_setting('zud.trusted', true), '') = '1' then return new; end if;
  if tg_op = 'INSERT' then
    new.blocked := false; new.block_reason := '';
  elsif new.blocked is distinct from old.blocked or new.block_reason is distinct from old.block_reason then
    raise exception 'Блокировку снимает только администратор';
  end if;
  return new;
end;
$$;
create trigger shops_blocked before insert or update on public.shops for each row execute function private.guard_blocked();
create trigger products_blocked before insert or update on public.products for each row execute function private.guard_blocked();

-- заблокированный человек не открывает новый магазин
create function private.guard_shop_owner() returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  if exists (select 1 from private.user_blocks b where b.user_id = new.owner_id and b.active) then
    raise exception 'Ваш аккаунт ограничен администратором. Напишите в поддержку';
  end if;
  return new;
end;
$$;
create trigger shops_owner_blocked before insert on public.shops for each row execute function private.guard_shop_owner();

-- заказ из приложения: заблокированный покупатель или магазин — отказ (place_order откатывается целиком, остатки не трогаются)
create function private.guard_new_order() returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  if new.source = 'app' then
    if exists (select 1 from private.user_blocks b where b.user_id = new.buyer_id and b.active) then
      raise exception 'Ваш аккаунт ограничен администратором. Напишите в поддержку';
    end if;
    if exists (select 1 from public.shops s where s.id = new.shop_id and s.blocked) then
      raise exception 'Магазин сейчас не принимает заказы';
    end if;
  end if;
  return new;
end;
$$;
create trigger orders_blocked before insert on public.orders for each row execute function private.guard_new_order();

-- решение по жалобе на отзыв принимает админ: магазин может только пожаловаться, но не скрыть отзыв сам
create function private.guard_review() returns trigger language plpgsql set search_path = ''
as $$
begin
  if coalesce(current_setting('zud.trusted', true), '') = '1' then return new; end if;
  if old.complaint ? 'decided_at' then
    new.complaint := old.complaint;                                     -- решение уже есть — не переписать
  elsif new.complaint is not null and new.complaint is distinct from old.complaint then
    new.complaint := (new.complaint - 'hidden' - 'decided_at' - 'decided_by' - 'note') || '{"status": "review"}'::jsonb;
  end if;
  return new;
end;
$$;
create trigger reviews_guard before update on public.reviews for each row execute function private.guard_review();

-- рейтинг магазина: скрытые админом отзывы не считаются ни в средней оценке, ни в количестве (раньше количество их учитывало)
create or replace function private.recount_rating() returns trigger language plpgsql security definer set search_path = ''
as $$
declare v_shop uuid := coalesce(new.shop_id, old.shop_id);
begin
  update public.shops s set (rating, rating_count) = (
    select coalesce(round(avg(r.rating)::numeric, 1), 0), count(*) from public.reviews r
    where r.shop_id = v_shop and r.created_at > now() - interval '90 days' and coalesce((r.complaint ->> 'hidden')::boolean, false) = false)
  where s.id = v_shop;
  return null;
end;
$$;

-- курьер: в сообщении о блокировке — причина
create or replace function private.me() returns public.couriers language plpgsql stable set search_path = ''
as $$
declare v public.couriers;
begin
  if auth.uid() is null then raise exception 'Нужно войти'; end if;
  select * into v from public.couriers where id = auth.uid();
  if not found then raise exception 'Сначала заполните анкету курьера'; end if;
  if v.status <> 'active' then
    raise exception 'Доступ курьера приостановлен%. Свяжитесь с поддержкой', coalesce(': ' || nullif(v.block_reason, ''), '');
  end if;
  return v;
end;
$$;

-- ---------- служебное ----------
create function private.is_admin() returns boolean language sql stable security definer set search_path = ''
as $$ select exists (select 1 from private.admins a where a.user_id = (select auth.uid()) and a.active); $$;

create function private.need_admin() returns uuid language plpgsql stable security definer set search_path = ''
as $$
begin
  if auth.uid() is null then raise exception 'Нужно войти'; end if;
  if not private.is_admin() then raise exception 'Нет доступа: это раздел администратора'; end if;
  return auth.uid();
end;
$$;

create function private.log(p_action text, p_kind text, p_target text, p_note text default '', p_data jsonb default '{}'::jsonb)
returns void language sql security definer set search_path = ''
as $$ insert into private.admin_log (admin_id, action, kind, target, note, data) values (auth.uid(), p_action, p_kind, p_target, left(coalesce(p_note, ''), 300), coalesce(p_data, '{}'::jsonb)); $$;

-- номер из служебной почты входа: 992XXXXXXXXX@zud.tj → XXXXXXXXX (9 цифр, как хранят приложения)
create function private.phone_of(p_email text) returns text language sql immutable set search_path = ''
as $$ select substring(p_email from '^992(\d{9})@zud\.tj$'); $$;

-- роли человека — как в начале файла
create function private.roles_of(p_id uuid, p_phone text) returns text[] language sql stable security definer set search_path = ''
as $$
  select array_remove(array[
    case when exists (select 1 from private.admins a where a.user_id = p_id and a.active) then 'admin' end,
    case when exists (select 1 from public.shops s where s.owner_id = p_id) then 'seller' end,
    case when p_phone is not null and exists (select 1 from public.shop_private sp
      where sp.data -> 'staff' @> jsonb_build_array(jsonb_build_object('phone', p_phone))) then 'staff' end,
    case when exists (select 1 from public.couriers c where c.id = p_id) then 'courier' end,
    case when exists (select 1 from public.orders o where o.buyer_id = p_id) then 'buyer' end
  ], null);
$$;

-- как человека зовут: анкета курьера → сотрудник магазина → имя в последнем заказе
create function private.name_of(p_id uuid, p_phone text) returns text language sql stable security definer set search_path = ''
as $$
  select coalesce(
    (select c.name from public.couriers c where c.id = p_id),
    (select st ->> 'name' from public.shop_private sp, jsonb_array_elements(coalesce(sp.data -> 'staff', '[]'::jsonb)) st
      where p_phone is not null and st ->> 'phone' = p_phone limit 1),
    (select nullif(o.customer ->> 'name', 'Покупатель') from public.orders o where o.buyer_id = p_id order by o.created_at desc limit 1),
    '');
$$;

-- коротко о человеке для списков и связей
create function private.uinfo(p_id uuid) returns jsonb language sql stable security definer set search_path = ''
as $$
  select jsonb_build_object('id', u.id, 'phone', private.phone_of(u.email), 'email', u.email, 'name', private.name_of(u.id, private.phone_of(u.email)))
  from auth.users u where u.id = p_id;
$$;

-- заказ для списков админа
create function private.order_row(o public.orders) returns jsonb language sql stable security definer set search_path = ''
as $$
  select jsonb_build_object(
    'id', o.id, 'no', o.no, 'status', o.status, 'step', o.courier_status, 'source', o.source, 'delivery', o.delivery,
    'shop', jsonb_build_object('id', s.id, 'name', s.name),
    'buyer_id', o.buyer_id, 'customer', jsonb_build_object('name', o.customer ->> 'name', 'phone', o.customer ->> 'phone', 'address', o.customer ->> 'address'),
    'courier_id', o.courier_id, 'courier', o.courier ->> 'name',
    'sum', o.sum, 'fee', o.fee, 'total', o.total, 'courier_fee', o.courier_fee, 'pay', o.pay, 'items', jsonb_array_length(o.items),
    'created_at', o.created_at, 'accepted_at', o.accepted_at, 'taken_at', o.courier_at, 'picked_at', o.picked_at,
    'delivered_at', o.delivered_at, 'received_at', o.received_at, 'cancel_reason', o.cancel_reason, 'problem', o.problem)
  from public.shops s where s.id = o.shop_id;
$$;

-- ---------- чтение ----------
/** Кто вошёл и админ ли он. Не падает для не-админа: экран входа покажет понятное сообщение. */
create function public.admin_me() returns jsonb language sql stable security definer set search_path = ''
as $$
  select jsonb_build_object('id', u.id, 'email', u.email, 'admin', private.is_admin())
  from auth.users u where u.id = (select auth.uid());
$$;

/** Главный экран: сколько людей, заказов, денег; график за 14 дней; сколько проблем. */
create function public.admin_overview() returns jsonb language plpgsql stable security definer set search_path = ''
as $$
declare d0 timestamptz := date_trunc('day', now()); r jsonb;
begin
  perform private.need_admin();
  select jsonb_build_object(
    'users', (select count(*) from auth.users),
    'users_today', (select count(*) from auth.users where created_at >= d0),
    'buyers', (select count(distinct buyer_id) from public.orders where buyer_id is not null),
    'shops', (select count(*) from public.shops),
    'shops_open', (select count(*) from public.shops where not paused and not blocked),
    'products', (select count(*) from public.products),
    'products_live', (select count(*) from public.products where active and not blocked and stock > 0),
    'couriers', (select count(*) from public.couriers),
    'couriers_online', (select count(*) from public.couriers where online and status = 'active'),
    'admins', (select count(*) from private.admins where active),
    'blocked', (select count(*) from private.user_blocks where active) + (select count(*) from public.shops where blocked)
               + (select count(*) from public.couriers where status = 'blocked'),
    'orders_today', (select count(*) from public.orders where created_at >= d0),
    'orders_7d', (select count(*) from public.orders where created_at >= d0 - interval '6 days'),
    'gmv_today', (select coalesce(sum(total), 0) from public.orders where created_at >= d0 and status <> 'cancelled'),
    'gmv_7d', (select coalesce(sum(total), 0) from public.orders where created_at >= d0 - interval '6 days' and status <> 'cancelled'),
    'fees_7d', (select coalesce(sum(fee), 0) from public.orders where created_at >= d0 - interval '6 days' and status <> 'cancelled'),
    'courier_pay_7d', (select coalesce(sum(courier_fee), 0) from public.orders where delivered_at >= d0 - interval '6 days'),
    'cancelled_7d', (select count(*) from public.orders where created_at >= d0 - interval '6 days' and status = 'cancelled'),
    'active', (select count(*) from public.orders where status in ('new', 'accepted', 'ready')
                 or (courier_status in ('going', 'at_shop', 'picked', 'at_client') and status <> 'cancelled')),
    'problems', (select count(*) from public.orders where problem is not null and not (problem ? 'resolved_at')),
    'complaints', (select count(*) from public.reviews where complaint is not null and not (complaint ? 'decided_at')),
    'by_status', (select coalesce(jsonb_object_agg(status, n), '{}'::jsonb) from (select status, count(*) n from public.orders group by status) t),
    'days', (select jsonb_agg(jsonb_build_object('d', d::date, 'orders', coalesce(x.n, 0), 'total', coalesce(x.total, 0), 'cancelled', coalesce(x.c, 0)) order by d)
             from generate_series(d0 - interval '13 days', d0, interval '1 day') d
             left join (select date_trunc('day', created_at) dd, count(*) n, sum(total) filter (where status <> 'cancelled') total,
                               count(*) filter (where status = 'cancelled') c
                        from public.orders where created_at >= d0 - interval '13 days' group by 1) x on x.dd = d))
  into r;
  return r;
end;
$$;

/** Все люди с ролями. p_q — номер, почта или имя; p_role — admin | seller | staff | courier | buyer | none | blocked. */
create function public.admin_users(p_q text default '', p_role text default '') returns jsonb language plpgsql stable security definer set search_path = ''
as $$
declare q text := lower(trim(coalesce(p_q, ''))); digits text := regexp_replace(coalesce(p_q, ''), '\D', '', 'g');
begin
  perform private.need_admin();
  if length(digits) > 9 and digits like '992%' then digits := substr(digits, 4); end if;
  return coalesce((
    select jsonb_agg(x order by x ->> 'created_at' desc) from (
      select jsonb_build_object('id', u.id, 'phone', ph, 'email', u.email, 'name', private.name_of(u.id, ph),
        'created_at', u.created_at, 'last_at', u.last_sign_in_at, 'roles', to_jsonb(rl), 'blocked', coalesce(b.active, false),
        'shop', (select jsonb_build_object('id', s.id, 'name', s.name, 'blocked', s.blocked) from public.shops s where s.owner_id = u.id),
        'courier', (select jsonb_build_object('status', c.status, 'online', c.online) from public.couriers c where c.id = u.id),
        'orders', (select count(*) from public.orders o where o.buyer_id = u.id)) x
      from auth.users u
      cross join lateral (select private.phone_of(u.email) ph) p
      cross join lateral (select private.roles_of(u.id, p.ph) rl) r
      left join private.user_blocks b on b.user_id = u.id
      where (q = '' or lower(coalesce(u.email, '')) like '%' || q || '%' or (digits <> '' and coalesce(p.ph, '') like '%' || digits || '%')
             or lower(private.name_of(u.id, p.ph)) like '%' || q || '%')
        and (coalesce(p_role, '') = '' or p_role = any (r.rl) or (p_role = 'none' and cardinality(r.rl) = 0)
             or (p_role = 'blocked' and coalesce(b.active, false)))
      limit 1000) t), '[]'::jsonb);
end;
$$;

/** Один человек и всё, что с ним связано: магазин, где он сотрудник, анкета курьера, заказы, доставки, отзывы, журнал. */
create function public.admin_user(p_id uuid) returns jsonb language plpgsql stable security definer set search_path = ''
as $$
declare u auth.users; ph text; r jsonb;
begin
  perform private.need_admin();
  select * into u from auth.users where id = p_id;
  if not found then raise exception 'Человек не найден'; end if;
  ph := private.phone_of(u.email);
  select jsonb_build_object(
    'id', u.id, 'phone', ph, 'email', u.email, 'name', private.name_of(u.id, ph), 'created_at', u.created_at, 'last_at', u.last_sign_in_at,
    'roles', to_jsonb(private.roles_of(u.id, ph)),
    'block', (select to_jsonb(b) - 'prev' from private.user_blocks b where b.user_id = u.id),
    'admin', (select jsonb_build_object('note', a.note, 'added_at', a.added_at) from private.admins a where a.user_id = u.id and a.active),
    'shop', (select jsonb_build_object('id', s.id, 'name', s.name, 'kind', s.kind, 'city', s.city, 'paused', s.paused, 'blocked', s.blocked) from public.shops s where s.owner_id = u.id),
    'staff_in', (select coalesce(jsonb_agg(jsonb_build_object('shop_id', s.id, 'shop', s.name, 'role', st ->> 'role', 'name', st ->> 'name')), '[]'::jsonb)
                 from public.shop_private sp join public.shops s on s.id = sp.shop_id, jsonb_array_elements(coalesce(sp.data -> 'staff', '[]'::jsonb)) st
                 where ph is not null and st ->> 'phone' = ph),
    'courier', (select to_jsonb(c) - 'lat' - 'lng' || jsonb_build_object('has_pos', c.lat is not null) from public.couriers c where c.id = u.id),
    'orders', (select coalesce(jsonb_agg(private.order_row(o) order by o.created_at desc), '[]'::jsonb)
               from (select * from public.orders where buyer_id = u.id order by created_at desc limit 100) o),
    'deliveries', (select coalesce(jsonb_agg(private.order_row(o) order by o.courier_at desc), '[]'::jsonb)
                   from (select * from public.orders where courier_id = u.id order by courier_at desc limit 100) o),
    'reviews', (select coalesce(jsonb_agg(jsonb_build_object('id', v.id, 'shop', s.name, 'shop_id', s.id, 'order_no', v.order_no, 'rating', v.rating, 'text', v.text, 'created_at', v.created_at)
                order by v.created_at desc), '[]'::jsonb) from public.reviews v join public.shops s on s.id = v.shop_id where v.buyer_id = u.id),
    'stats', jsonb_build_object(
      'orders', (select count(*) from public.orders where buyer_id = u.id),
      'spent', (select coalesce(sum(total), 0) from public.orders where buyer_id = u.id and status <> 'cancelled'),
      'cancelled', (select count(*) from public.orders where buyer_id = u.id and status = 'cancelled'),
      'problems', (select count(*) from public.orders where buyer_id = u.id and problem is not null),
      'deliveries', (select count(*) from public.orders where courier_id = u.id and courier_status = 'delivered'),
      'earned', (select coalesce(sum(courier_fee), 0) from public.orders where courier_id = u.id and courier_status = 'delivered')),
    'log', (select coalesce(jsonb_agg(jsonb_build_object('at', l.at, 'action', l.action, 'note', l.note, 'by', a.email) order by l.at desc), '[]'::jsonb)
            from private.admin_log l left join auth.users a on a.id = l.admin_id where (l.kind in ('user', 'courier', 'admin')) and l.target = u.id::text))
  into r;
  return r;
end;
$$;

/** Все магазины: владелец, сотрудники, товары, заказы, выручка за 30 дней. */
create function public.admin_shops(p_q text default '') returns jsonb language plpgsql stable security definer set search_path = ''
as $$
declare q text := lower(trim(coalesce(p_q, '')));
begin
  perform private.need_admin();
  return coalesce((select jsonb_agg(jsonb_build_object(
      'id', s.id, 'name', s.name, 'kind', s.kind, 'city', s.city, 'address', s.address, 'phone', s.phone, 'logo', s.logo,
      'paused', s.paused, 'blocked', s.blocked, 'block_reason', s.block_reason, 'rating', s.rating, 'rating_count', s.rating_count,
      'has_pin', s.lat is not null and s.lng is not null, 'created_at', s.created_at, 'owner', private.uinfo(s.owner_id),
      'staff', (select coalesce(jsonb_array_length(sp.data -> 'staff'), 0) from public.shop_private sp where sp.shop_id = s.id),
      'products', (select count(*) from public.products p where p.shop_id = s.id),
      'products_live', (select count(*) from public.products p where p.shop_id = s.id and p.active and not p.blocked and p.stock > 0),
      'orders_30d', (select count(*) from public.orders o where o.shop_id = s.id and o.created_at > now() - interval '30 days'),
      'revenue_30d', (select coalesce(sum(o.sum), 0) from public.orders o where o.shop_id = s.id and o.created_at > now() - interval '30 days' and o.status <> 'cancelled'),
      'active', (select count(*) from public.orders o where o.shop_id = s.id and o.status in ('new', 'accepted', 'ready')))
    order by s.created_at desc)
    from public.shops s
    where q = '' or lower(s.name) like '%' || q || '%' or lower(s.city) like '%' || q || '%' or s.phone like '%' || q || '%'), '[]'::jsonb);
end;
$$;

/** Магазин целиком: настройки, владелец, сотрудники (и есть ли у них вход), товары, заказы, отзывы, расходы, журнал. */
create function public.admin_shop(p_id uuid) returns jsonb language plpgsql stable security definer set search_path = ''
as $$
declare s public.shops; r jsonb;
begin
  perform private.need_admin();
  select * into s from public.shops where id = p_id;
  if not found then raise exception 'Магазин не найден'; end if;
  select jsonb_build_object(
    'shop', to_jsonb(s), 'owner', private.uinfo(s.owner_id),
    'staff', (select coalesce(jsonb_agg(st || jsonb_build_object('user', (select private.uinfo(u.id) from auth.users u where private.phone_of(u.email) = st ->> 'phone'))), '[]'::jsonb)
              from public.shop_private sp, jsonb_array_elements(coalesce(sp.data -> 'staff', '[]'::jsonb)) st where sp.shop_id = s.id),
    'alif', (select sp.data -> 'alif' from public.shop_private sp where sp.shop_id = s.id),
    'products', (select coalesce(jsonb_agg(jsonb_build_object('id', p.id, 'sku', p.sku, 'name', p.name, 'cat', p.cat, 'price', p.price, 'unit', p.unit, 'stock', p.stock,
                   'active', p.active, 'blocked', p.blocked, 'block_reason', p.block_reason, 'img', p.data -> 'imgs' ->> 0, 'expiry', p.expiry) order by p.created_at desc), '[]'::jsonb)
                 from public.products p where p.shop_id = s.id),
    'orders', (select coalesce(jsonb_agg(private.order_row(o) order by o.created_at desc), '[]'::jsonb)
               from (select * from public.orders where shop_id = s.id order by created_at desc limit 150) o),
    'reviews', (select coalesce(jsonb_agg(to_jsonb(v) order by v.created_at desc), '[]'::jsonb) from public.reviews v where v.shop_id = s.id),
    'stats', jsonb_build_object(
      'orders', (select count(*) from public.orders where shop_id = s.id),
      'app_orders', (select count(*) from public.orders where shop_id = s.id and source = 'app'),
      'shop_sales', (select count(*) from public.orders where shop_id = s.id and source = 'shop'),
      'revenue', (select coalesce(sum(sum), 0) from public.orders where shop_id = s.id and status <> 'cancelled'),
      'cancelled', (select count(*) from public.orders where shop_id = s.id and status = 'cancelled'),
      'expenses_30d', (select coalesce(sum(amount), 0) from public.expenses where shop_id = s.id and spent_on > current_date - 30),
      'avg_accept_min', (select round(avg(extract(epoch from accepted_at - created_at) / 60)::numeric, 1) from public.orders
                         where shop_id = s.id and source = 'app' and accepted_at is not null and created_at > now() - interval '30 days')),
    'log', (select coalesce(jsonb_agg(jsonb_build_object('at', l.at, 'action', l.action, 'note', l.note, 'by', a.email) order by l.at desc), '[]'::jsonb)
            from private.admin_log l left join auth.users a on a.id = l.admin_id where l.kind = 'shop' and l.target = s.id::text))
  into r;
  return r;
end;
$$;

/** Товары всех магазинов. p_q — название или артикул; p_filter — blocked | off | empty | expired. */
create function public.admin_products(p_q text default '', p_filter text default '') returns jsonb language plpgsql stable security definer set search_path = ''
as $$
declare q text := lower(trim(coalesce(p_q, '')));
begin
  perform private.need_admin();
  return coalesce((select jsonb_agg(x order by x ->> 'created_at' desc) from (
    select jsonb_build_object('id', p.id, 'sku', p.sku, 'name', p.name, 'cat', p.cat, 'price', p.price, 'old_price', p.old_price, 'unit', p.unit,
      'stock', p.stock, 'active', p.active, 'blocked', p.blocked, 'block_reason', p.block_reason, 'expiry', p.expiry, 'img', p.data -> 'imgs' ->> 0,
      'created_at', p.created_at, 'shop', jsonb_build_object('id', s.id, 'name', s.name, 'blocked', s.blocked),
      'sold_30d', (select coalesce(sum((i ->> 'qty')::numeric), 0) from public.orders o, jsonb_array_elements(o.items) i
                   where o.shop_id = p.shop_id and o.created_at > now() - interval '30 days' and o.status <> 'cancelled' and i ->> 'pid' = p.id)) x
    from public.products p join public.shops s on s.id = p.shop_id
    where (q = '' or lower(p.name) like '%' || q || '%' or p.sku::text = q or lower(p.cat) like '%' || q || '%')
      and (coalesce(p_filter, '') = '' or (p_filter = 'blocked' and p.blocked) or (p_filter = 'off' and not p.active)
           or (p_filter = 'empty' and p.stock <= 0) or (p_filter = 'expired' and p.expiry < current_date))
    limit 1000) t), '[]'::jsonb);
end;
$$;

/** Заказы с фильтрами. p_status — new | accepted | ready | done | cancelled | active | problem | delivering. */
create function public.admin_orders(p_status text default '', p_q text default '', p_shop uuid default null, p_person uuid default null,
                                    p_from date default null, p_to date default null)
returns jsonb language plpgsql stable security definer set search_path = ''
as $$
declare q text := lower(trim(coalesce(p_q, ''))); digits text := regexp_replace(coalesce(p_q, ''), '\D', '', 'g');
begin
  perform private.need_admin();
  return coalesce((select jsonb_agg(private.order_row(o) order by o.created_at desc) from (
    select * from public.orders o
    where (p_shop is null or o.shop_id = p_shop)
      and (p_person is null or o.buyer_id = p_person or o.courier_id = p_person)
      and (p_from is null or o.created_at >= p_from) and (p_to is null or o.created_at < p_to + 1)
      and (q = '' or o.no::text = digits or (length(digits) >= 4 and regexp_replace(coalesce(o.customer ->> 'phone', ''), '\D', '', 'g') like '%' || digits || '%')
           or lower(coalesce(o.customer ->> 'name', '')) like '%' || q || '%' or lower(coalesce(o.courier ->> 'name', '')) like '%' || q || '%')
      and (coalesce(p_status, '') = '' or o.status = p_status
           or (p_status = 'active' and (o.status in ('new', 'accepted', 'ready') or (o.courier_status in ('going', 'at_shop', 'picked', 'at_client') and o.status <> 'cancelled')))
           or (p_status = 'delivering' and o.courier_status in ('going', 'at_shop', 'picked', 'at_client') and o.status <> 'cancelled')
           or (p_status = 'problem' and o.problem is not null and not (o.problem ? 'resolved_at')))
    order by o.created_at desc limit 500) o), '[]'::jsonb);
end;
$$;

/** Заказ целиком: состав, деньги, все этапы со временем, покупатель, магазин, курьер, код, отзыв, журнал. */
create function public.admin_order(p_id text) returns jsonb language plpgsql stable security definer set search_path = ''
as $$
declare o public.orders; r jsonb;
begin
  perform private.need_admin();
  select * into o from public.orders where id = p_id;
  if not found then raise exception 'Заказ не найден'; end if;
  select jsonb_build_object(
    'order', to_jsonb(o), 'buyer', private.uinfo(o.buyer_id), 'courier_user', private.uinfo(o.courier_id),
    'shop', (select jsonb_build_object('id', s.id, 'name', s.name, 'phone', s.phone, 'address', s.address, 'blocked', s.blocked, 'owner', private.uinfo(s.owner_id))
             from public.shops s where s.id = o.shop_id),
    'code', (select c.code from private.order_codes c where c.order_id = o.id),
    'costs', (select op.costs from public.order_private op where op.order_id = o.id),
    'review', (select to_jsonb(v) from public.reviews v where v.order_id = o.id),
    'log', (select coalesce(jsonb_agg(jsonb_build_object('at', l.at, 'action', l.action, 'note', l.note, 'by', a.email) order by l.at desc), '[]'::jsonb)
            from private.admin_log l left join auth.users a on a.id = l.admin_id where l.kind = 'order' and l.target = o.id))
  into r;
  return r;
end;
$$;

/** Все курьеры: на линии ли, где и когда были, текущий заказ, доставки и заработок за 7 дней, наличные на руках сегодня. */
create function public.admin_couriers() returns jsonb language plpgsql stable security definer set search_path = ''
as $$
declare d0 timestamptz := date_trunc('day', now());
begin
  perform private.need_admin();
  return coalesce((select jsonb_agg(jsonb_build_object(
      'id', c.id, 'name', c.name, 'phone', c.phone, 'car', c.car, 'plate', c.plate, 'status', c.status, 'block_reason', c.block_reason,
      'online', c.online, 'lat', c.lat, 'lng', c.lng, 'loc_at', c.loc_at, 'rating', c.rating, 'rating_count', c.rating_count, 'created_at', c.created_at,
      'account', private.uinfo(c.id),
      'job', (select jsonb_build_object('id', o.id, 'no', o.no, 'step', o.courier_status, 'shop', s.name, 'taken_at', o.courier_at)
              from public.orders o join public.shops s on s.id = o.shop_id
              where o.courier_id = c.id and o.courier_status in ('going', 'at_shop', 'picked', 'at_client') and o.status <> 'cancelled'
              order by o.courier_at desc limit 1),
      'done_7d', (select count(*) from public.orders o where o.courier_id = c.id and o.delivered_at >= d0 - interval '6 days'),
      'earned_7d', (select coalesce(sum(o.courier_fee), 0) from public.orders o where o.courier_id = c.id and o.delivered_at >= d0 - interval '6 days'),
      'cash_today', (select coalesce(sum(o.cash_taken), 0) from public.orders o where o.courier_id = c.id and o.delivered_at >= d0),
      'returned', (select count(*) from public.orders o where o.courier_id = c.id and o.courier_status = 'returned'))
    order by c.online desc, c.loc_at desc nulls last) from public.couriers c), '[]'::jsonb);
end;
$$;

/** Карта: курьеры на линии и заказы в работе с точками магазина и покупателя. */
create function public.admin_map() returns jsonb language plpgsql stable security definer set search_path = ''
as $$
begin
  perform private.need_admin();
  return jsonb_build_object(
    'couriers', (select coalesce(jsonb_agg(jsonb_build_object('id', c.id, 'name', c.name, 'lat', c.lat, 'lng', c.lng, 'loc_at', c.loc_at,
                   'busy', exists (select 1 from public.orders o where o.courier_id = c.id and o.courier_status in ('going', 'at_shop', 'picked', 'at_client') and o.status <> 'cancelled'))), '[]'::jsonb)
                 from public.couriers c where c.online and c.lat is not null),
    'shops', (select coalesce(jsonb_agg(jsonb_build_object('id', s.id, 'name', s.name, 'lat', s.lat, 'lng', s.lng, 'paused', s.paused, 'blocked', s.blocked)), '[]'::jsonb)
              from public.shops s where s.lat is not null),
    'orders', (select coalesce(jsonb_agg(jsonb_build_object('id', o.id, 'no', o.no, 'status', o.status, 'step', o.courier_status, 'courier_id', o.courier_id,
                 'shop_lat', s.lat, 'shop_lng', s.lng, 'to_lat', o.customer -> 'addr' -> 'lat', 'to_lng', o.customer -> 'addr' -> 'lng')), '[]'::jsonb)
               from public.orders o join public.shops s on s.id = o.shop_id
               where o.source = 'app' and o.created_at > now() - interval '1 day'
                 and (o.status in ('new', 'accepted', 'ready') or (o.courier_status in ('going', 'at_shop', 'picked', 'at_client') and o.status <> 'cancelled'))));
end;
$$;

/** Отзывы всех магазинов. p_filter — complaints (жалобы без решения) | hidden | low (1–2 звезды). */
create function public.admin_reviews(p_filter text default '') returns jsonb language plpgsql stable security definer set search_path = ''
as $$
begin
  perform private.need_admin();
  return coalesce((select jsonb_agg(to_jsonb(v) || jsonb_build_object('shop', jsonb_build_object('id', s.id, 'name', s.name), 'buyer', private.uinfo(v.buyer_id))
                   order by (v.complaint is not null and not (v.complaint ? 'decided_at')) desc, v.created_at desc)
    from public.reviews v join public.shops s on s.id = v.shop_id
    where coalesce(p_filter, '') = '' or (p_filter = 'complaints' and v.complaint is not null and not (v.complaint ? 'decided_at'))
       or (p_filter = 'hidden' and coalesce((v.complaint ->> 'hidden')::boolean, false)) or (p_filter = 'low' and v.rating <= 2)), '[]'::jsonb);
end;
$$;

/**
 * Проверки: что требует внимания прямо сейчас. Каждая — уровень (high — срочно, mid — сегодня, low — когда будет время),
 * что случилось, почему важно и куда нажать (target).
 */
create function public.admin_checks() returns jsonb language plpgsql stable security definer set search_path = ''
as $$
begin
  perform private.need_admin();
  return coalesce((select jsonb_agg(c order by case c ->> 'level' when 'high' then 0 when 'mid' then 1 else 2 end, c ->> 'at' desc nulls last) from (
    -- магазин не принимает заказ
    select jsonb_build_object('level', 'high', 'kind', 'shop_silent', 'title', format('Магазин молчит: заказ № %s', o.no),
      'text', format('«%s» не принял заказ уже %s мин. Позвоните в магазин: %s', s.name, floor(extract(epoch from now() - o.created_at) / 60), nullif(s.phone, '')),
      'target', jsonb_build_object('kind', 'order', 'id', o.id), 'at', o.created_at) c
    from public.orders o join public.shops s on s.id = o.shop_id
    where o.source = 'app' and o.status = 'new' and o.created_at < now() - interval '10 minutes' and o.created_at > now() - interval '2 days'
    union all
    -- заказ собран, а курьера нет
    select jsonb_build_object('level', 'high', 'kind', 'no_courier', 'title', format('Нет курьера: заказ № %s', o.no),
      'text', format('Магазин принял заказ %s мин назад, ни один курьер его не взял. Курьеров на линии: %s',
                     floor(extract(epoch from now() - coalesce(o.accepted_at, o.created_at)) / 60),
                     (select count(*) from public.couriers k where k.online and k.status = 'active')),
      'target', jsonb_build_object('kind', 'order', 'id', o.id), 'at', o.created_at)
    from public.orders o
    where o.source = 'app' and o.delivery = 'courier' and o.courier_id is null and o.status in ('accepted', 'ready')
      and coalesce(o.accepted_at, o.created_at) < now() - interval '20 minutes' and o.created_at > now() - interval '2 days'
    union all
    -- доставка идёт слишком долго
    select jsonb_build_object('level', 'mid', 'kind', 'slow', 'title', format('Долгая доставка: заказ № %s', o.no),
      'text', format('Курьер %s везёт заказ уже %s мин', coalesce(o.courier ->> 'name', ''), floor(extract(epoch from now() - o.courier_at) / 60)),
      'target', jsonb_build_object('kind', 'order', 'id', o.id), 'at', o.courier_at)
    from public.orders o
    where o.courier_status in ('going', 'at_shop', 'picked', 'at_client') and o.status <> 'cancelled' and o.courier_at < now() - interval '90 minutes'
    union all
    -- покупатель или курьер сообщил о проблеме
    select jsonb_build_object('level', 'high', 'kind', 'problem', 'title', format('Проблема: заказ № %s', o.no),
      'text', concat_ws(' — ', o.problem ->> 'reason', nullif(o.problem ->> 'text', '')),
      'target', jsonb_build_object('kind', 'order', 'id', o.id), 'at', o.problem ->> 'ts')
    from public.orders o where o.problem is not null and not (o.problem ? 'resolved_at')
    union all
    -- курьер на линии, но телефон не присылает место
    select jsonb_build_object('level', 'mid', 'kind', 'courier_lost', 'title', format('Курьер без связи: %s', k.name),
      'text', case when k.loc_at is null then 'На линии, но место ни разу не пришло — включите ему геолокацию'
                   else format('Место не обновлялось %s мин — нет интернета или приложение закрыто', floor(extract(epoch from now() - k.loc_at) / 60)) end,
      'target', jsonb_build_object('kind', 'user', 'id', k.id), 'at', k.loc_at)
    from public.couriers k where k.online and k.status = 'active' and (k.loc_at is null or k.loc_at < now() - interval '15 minutes')
    union all
    -- заблокированный курьер ещё везёт заказ
    select jsonb_build_object('level', 'high', 'kind', 'blocked_busy', 'title', format('Заблокированный курьер с заказом № %s', o.no),
      'text', format('%s заблокирован, а заказ у него. Снимите курьера с заказа или закройте заказ', coalesce(o.courier ->> 'name', '')),
      'target', jsonb_build_object('kind', 'order', 'id', o.id), 'at', o.courier_at)
    from public.orders o join public.couriers k on k.id = o.courier_id
    where k.status = 'blocked' and o.courier_status in ('going', 'at_shop', 'picked', 'at_client') and o.status <> 'cancelled'
    union all
    -- заблокированный магазин, а заказы в работе
    select jsonb_build_object('level', 'high', 'kind', 'blocked_shop_orders', 'title', format('Заблокированный магазин с заказами: %s', s.name),
      'text', format('Заказов в работе: %s. Решите, отменить их или дать магазину доделать', count(*)),
      'target', jsonb_build_object('kind', 'shop', 'id', s.id), 'at', max(o.created_at))
    from public.shops s join public.orders o on o.shop_id = s.id
    where s.blocked and o.status in ('new', 'accepted', 'ready') group by s.id
    union all
    -- жалоба магазина на отзыв ждёт решения
    select jsonb_build_object('level', 'mid', 'kind', 'complaint', 'title', format('Жалоба на отзыв: %s', s.name),
      'text', format('Отзыв %s★ к заказу № %s. Причина: %s', v.rating, v.order_no, v.complaint ->> 'reason'),
      'target', jsonb_build_object('kind', 'review', 'id', v.id), 'at', v.created_at)
    from public.reviews v join public.shops s on s.id = v.shop_id where v.complaint is not null and not (v.complaint ? 'decided_at')
    union all
    -- у магазина нет метки на карте
    select jsonb_build_object('level', 'mid', 'kind', 'no_pin', 'title', format('Магазин без точки на карте: %s', s.name),
      'text', 'Курьер не построит маршрут, а цена доставки считается примерно. Попросите магазин поставить точку в настройках',
      'target', jsonb_build_object('kind', 'shop', 'id', s.id), 'at', s.created_at)
    from public.shops s where (s.lat is null or s.lng is null) and not s.blocked
    union all
    -- у магазина нет телефона
    select jsonb_build_object('level', 'low', 'kind', 'no_phone', 'title', format('Магазин без телефона: %s', s.name),
      'text', 'Курьер и покупатель не смогут позвонить в магазин',
      'target', jsonb_build_object('kind', 'shop', 'id', s.id), 'at', s.created_at)
    from public.shops s where coalesce(s.phone, '') = '' and not s.blocked
    union all
    -- открытый магазин, а купить нечего
    select jsonb_build_object('level', 'low', 'kind', 'empty_shop', 'title', format('Пустая витрина: %s', s.name),
      'text', 'Магазин открыт, но нет ни одного товара в наличии — покупатель уйдёт',
      'target', jsonb_build_object('kind', 'shop', 'id', s.id), 'at', s.created_at)
    from public.shops s where not s.paused and not s.blocked
      and not exists (select 1 from public.products p where p.shop_id = s.id and p.active and not p.blocked and p.stock > 0)
    union all
    -- просроченный товар в продаже (покупатель его не видит в заказе, но витрина выглядит неряшливо)
    select jsonb_build_object('level', 'mid', 'kind', 'expired', 'title', format('Просрочка в продаже: %s', s.name),
      'text', format('Товаров с истёкшим сроком: %s (%s)', count(*), string_agg(p.name, ', ' order by p.name)),
      'target', jsonb_build_object('kind', 'shop', 'id', s.id), 'at', min(p.expiry)::timestamptz)
    from public.products p join public.shops s on s.id = p.shop_id
    where p.active and not p.blocked and p.expiry < current_date group by s.id
    union all
    -- низкий рейтинг
    select jsonb_build_object('level', 'mid', 'kind', 'low_rating', 'title', format('Низкий рейтинг курьера: %s — %s★', k.name, k.rating),
      'text', format('Оценок: %s. Поговорите с курьером', k.rating_count), 'target', jsonb_build_object('kind', 'user', 'id', k.id), 'at', k.updated_at)
    from public.couriers k where k.rating_count >= 5 and k.rating < 3.5 and k.status = 'active'
    union all
    select jsonb_build_object('level', 'low', 'kind', 'low_rating', 'title', format('Низкий рейтинг магазина: %s — %s★', s.name, s.rating),
      'text', format('Оценок за 3 месяца: %s. Посмотрите отзывы', s.rating_count), 'target', jsonb_build_object('kind', 'shop', 'id', s.id), 'at', s.updated_at)
    from public.shops s where s.rating_count >= 5 and s.rating < 3.5 and not s.blocked
    union all
    -- покупатель часто отменяет
    select jsonb_build_object('level', 'low', 'kind', 'cancels', 'title', 'Покупатель часто отменяет заказы',
      'text', format('%s из %s заказов за 30 дней отменены', sum((o.status = 'cancelled')::int), count(*)),
      'target', jsonb_build_object('kind', 'user', 'id', o.buyer_id), 'at', max(o.created_at))
    from public.orders o where o.buyer_id is not null and o.created_at > now() - interval '30 days'
    group by o.buyer_id having count(*) >= 4 and sum((o.status = 'cancelled')::int) * 2 >= count(*)
    union all
    -- сотрудник магазина без входа (его номер ни разу не входил)
    select jsonb_build_object('level', 'low', 'kind', 'staff_no_account', 'title', format('Сотрудник ещё не входил: %s', st ->> 'name'),
      'text', format('Магазин «%s», номер +992 %s. Пусть войдёт в кабинет продавца под своим номером', s.name, st ->> 'phone'),
      'target', jsonb_build_object('kind', 'shop', 'id', s.id), 'at', null)
    from public.shop_private sp join public.shops s on s.id = sp.shop_id, jsonb_array_elements(coalesce(sp.data -> 'staff', '[]'::jsonb)) st
    where not exists (select 1 from auth.users u where private.phone_of(u.email) = st ->> 'phone')
  ) t), '[]'::jsonb);
end;
$$;

/** Журнал действий админов: кто, когда, что сделал. */
create function public.admin_log(p_limit integer default 200) returns jsonb language plpgsql stable security definer set search_path = ''
as $$
begin
  perform private.need_admin();
  return coalesce((select jsonb_agg(jsonb_build_object('id', l.id, 'at', l.at, 'by', a.email, 'action', l.action, 'kind', l.kind, 'target', l.target, 'note', l.note, 'data', l.data) order by l.at desc)
    from (select * from private.admin_log order by at desc limit least(greatest(p_limit, 1), 1000)) l left join auth.users a on a.id = l.admin_id), '[]'::jsonb);
end;
$$;

/** Админы и настройки сервиса (только чтение — меняются в базе). */
create function public.admin_system() returns jsonb language plpgsql stable security definer set search_path = ''
as $$
begin
  perform private.need_admin();
  return jsonb_build_object(
    'admins', (select coalesce(jsonb_agg(jsonb_build_object('id', a.user_id, 'email', u.email, 'note', a.note, 'added_at', a.added_at, 'me', a.user_id = auth.uid()) order by a.added_at), '[]'::jsonb)
               from private.admins a join auth.users u on u.id = a.user_id where a.active),
    'zone_open', private.zone_open(), 'courier_share', private.courier_share(), 'courier_radius', private.courier_radius());
end;
$$;

-- ---------- действия ----------
/** Заблокировать или разблокировать магазин. Заблокированный магазин не виден покупателям и не получает заказов. */
create function public.admin_shop_block(p_shop uuid, p_on boolean, p_reason text default '') returns void language plpgsql security definer set search_path = ''
as $$
begin
  perform private.need_admin(); perform private.trust();
  if p_on and coalesce(trim(p_reason), '') = '' then raise exception 'Напишите причину — её увидит владелец магазина'; end if;
  update public.shops set blocked = p_on, block_reason = case when p_on then left(trim(p_reason), 200) else '' end where id = p_shop;
  if not found then raise exception 'Магазин не найден'; end if;
  perform private.log(case when p_on then 'shop_block' else 'shop_unblock' end, 'shop', p_shop::text, p_reason);
end;
$$;

/** Скрыть товар из продажи (нарушение правил) или вернуть. */
create function public.admin_product_block(p_product text, p_on boolean, p_reason text default '') returns void language plpgsql security definer set search_path = ''
as $$
declare v_shop uuid;
begin
  perform private.need_admin(); perform private.trust();
  if p_on and coalesce(trim(p_reason), '') = '' then raise exception 'Напишите причину — её увидит магазин'; end if;
  update public.products set blocked = p_on, block_reason = case when p_on then left(trim(p_reason), 200) else '' end where id = p_product returning shop_id into v_shop;
  if not found then raise exception 'Товар не найден'; end if;
  perform private.log(case when p_on then 'product_block' else 'product_unblock' end, 'product', p_product, p_reason, jsonb_build_object('shop', v_shop));
end;
$$;

/** Заблокировать или разблокировать курьера: не видит заказы и не может взять новый. */
create function public.admin_courier_block(p_courier uuid, p_on boolean, p_reason text default '') returns void language plpgsql security definer set search_path = ''
as $$
begin
  perform private.need_admin();
  if p_on and coalesce(trim(p_reason), '') = '' then raise exception 'Напишите причину — её увидит курьер'; end if;
  update public.couriers set status = case when p_on then 'blocked' else 'active' end, online = case when p_on then false else online end,
    block_reason = case when p_on then left(trim(p_reason), 200) else '' end where id = p_courier;
  if not found then raise exception 'Курьер не найден'; end if;
  perform private.log(case when p_on then 'courier_block' else 'courier_unblock' end, 'courier', p_courier::text, p_reason);
end;
$$;

/**
 * Заблокировать человека целиком: не может заказывать, работать курьером, открыть магазин; его магазин скрыт.
 * Разблокировка возвращает магазин и курьера в то состояние, что было до блокировки.
 */
create function public.admin_user_block(p_user uuid, p_on boolean, p_reason text default '') returns void language plpgsql security definer set search_path = ''
as $$
declare b private.user_blocks; v_prev jsonb;
begin
  perform private.need_admin(); perform private.trust();
  if p_user = auth.uid() then raise exception 'Нельзя заблокировать самого себя'; end if;
  if not exists (select 1 from auth.users where id = p_user) then raise exception 'Человек не найден'; end if;
  select * into b from private.user_blocks where user_id = p_user;
  if p_on then
    if coalesce(trim(p_reason), '') = '' then raise exception 'Напишите причину блокировки'; end if;
    if b.active then return; end if;
    v_prev := jsonb_build_object(
      'shop', (select jsonb_build_object('blocked', s.blocked, 'reason', s.block_reason) from public.shops s where s.owner_id = p_user),
      'courier', (select jsonb_build_object('status', c.status, 'reason', c.block_reason) from public.couriers c where c.id = p_user));
    insert into private.user_blocks (user_id, active, reason, prev, at, by) values (p_user, true, left(trim(p_reason), 200), v_prev, now(), auth.uid())
    on conflict (user_id) do update set active = true, reason = excluded.reason, prev = excluded.prev, at = now(), by = auth.uid();
    update public.shops set blocked = true, block_reason = 'Аккаунт владельца заблокирован: ' || left(trim(p_reason), 160) where owner_id = p_user and not blocked;
    update public.couriers set status = 'blocked', online = false, block_reason = left(trim(p_reason), 200) where id = p_user and status <> 'blocked';
  else
    if b.user_id is null or not b.active then return; end if;
    update private.user_blocks set active = false, at = now(), by = auth.uid() where user_id = p_user;
    update public.shops set blocked = coalesce((b.prev -> 'shop' ->> 'blocked')::boolean, false), block_reason = coalesce(b.prev -> 'shop' ->> 'reason', '') where owner_id = p_user;
    update public.couriers set status = coalesce(b.prev -> 'courier' ->> 'status', 'active'), block_reason = coalesce(b.prev -> 'courier' ->> 'reason', '') where id = p_user;
  end if;
  perform private.log(case when p_on then 'user_block' else 'user_unblock' end, 'user', p_user::text, p_reason);
end;
$$;

/** Отменить заказ. Если товар ещё в магазине — вернуть остатки. */
create function public.admin_order_cancel(p_order text, p_reason text) returns void language plpgsql security definer set search_path = ''
as $$
declare v public.orders; i jsonb;
begin
  perform private.need_admin(); perform private.trust();
  if coalesce(trim(p_reason), '') = '' then raise exception 'Напишите причину — её увидят покупатель, магазин и курьер'; end if;
  select * into v from public.orders where id = p_order for update;
  if not found then raise exception 'Заказ не найден'; end if;
  if v.status = 'cancelled' then raise exception 'Заказ уже отменён'; end if;
  if v.courier_status = 'delivered' or v.received_at is not null then raise exception 'Заказ уже получен — отменить нельзя'; end if;
  -- товар не покидал магазин: возвращаем остатки (продажи в магазине не трогаем — их ведёт сам магазин)
  if v.source = 'app' and v.status in ('new', 'accepted', 'ready') and coalesce(v.courier_status, 'going') in ('going', 'at_shop') then
    for i in select * from jsonb_array_elements(v.items) loop
      update public.products set stock = stock + (i ->> 'qty')::numeric where id = i ->> 'pid';
    end loop;
  end if;
  update public.orders set status = 'cancelled', cancel_reason = 'Отменил администратор: ' || left(trim(p_reason), 200) where id = v.id;
  perform private.log('order_cancel', 'order', v.id, p_reason, jsonb_build_object('no', v.no));
end;
$$;

/** Снять курьера с заказа (пока он не забрал товар): заказ снова в ленте у всех курьеров. */
create function public.admin_order_release(p_order text, p_reason text default '') returns void language plpgsql security definer set search_path = ''
as $$
declare v public.orders;
begin
  perform private.need_admin(); perform private.trust();
  update public.orders set courier_id = null, courier = null, courier_status = null, courier_at = null, courier_fee = null
  where id = p_order and courier_id is not null and courier_status in ('going', 'at_shop') and status <> 'cancelled' returning * into v;
  if not found then raise exception 'Снять можно только курьера, который ещё не забрал заказ'; end if;
  perform private.log('order_release', 'order', p_order, p_reason, jsonb_build_object('no', v.no));
end;
$$;

/** Закрыть как доставленный — если курьер передал заказ, но не отметил в приложении. */
create function public.admin_order_delivered(p_order text, p_reason text) returns void language plpgsql security definer set search_path = ''
as $$
declare v public.orders;
begin
  perform private.need_admin(); perform private.trust();
  if coalesce(trim(p_reason), '') = '' then raise exception 'Напишите, кто подтвердил получение'; end if;
  update public.orders set status = 'done', courier_status = case when courier_id is not null then 'delivered' else courier_status end,
    delivered_at = case when courier_id is not null then coalesce(delivered_at, now()) else delivered_at end,
    received_at = coalesce(received_at, now()), cash_taken = case when courier_id is not null and pay = 'cash' then coalesce(cash_taken, total) else cash_taken end
  where id = p_order and status <> 'cancelled' and received_at is null returning * into v;
  if not found then raise exception 'Заказ уже закрыт или отменён'; end if;
  perform private.log('order_delivered', 'order', p_order, p_reason, jsonb_build_object('no', v.no));
end;
$$;

/** Проблема по заказу решена: что сделали. */
create function public.admin_order_resolve(p_order text, p_note text) returns void language plpgsql security definer set search_path = ''
as $$
begin
  perform private.need_admin(); perform private.trust();
  if coalesce(trim(p_note), '') = '' then raise exception 'Напишите, как решили проблему'; end if;
  update public.orders set problem = coalesce(problem, jsonb_build_object('reason', 'Курьер вернул заказ', 'ts', now()))
      || jsonb_build_object('resolved_at', now(), 'resolved_note', left(trim(p_note), 300), 'resolved_by', auth.uid())
  where id = p_order and (problem is not null or courier_status = 'returned');
  if not found then raise exception 'У заказа нет проблемы'; end if;
  perform private.log('order_resolve', 'order', p_order, p_note);
end;
$$;

/** Решение по жалобе магазина на отзыв: скрыть отзыв (жалоба принята) или оставить (отклонена). Можно и без жалобы. */
create function public.admin_review_decide(p_review uuid, p_hide boolean, p_note text default '') returns void language plpgsql security definer set search_path = ''
as $$
begin
  perform private.need_admin(); perform private.trust();
  update public.reviews set complaint = coalesce(complaint, '{}'::jsonb) || jsonb_build_object('hidden', p_hide, 'status', case when p_hide then 'accepted' else 'rejected' end,
    'decided_at', now(), 'decided_by', auth.uid(), 'note', left(coalesce(p_note, ''), 300))
  where id = p_review;
  if not found then raise exception 'Отзыв не найден'; end if;
  perform private.log(case when p_hide then 'review_hide' else 'review_keep' end, 'review', p_review::text, p_note);
end;
$$;

/** Дать или забрать права админа. Себя снять нельзя — так в системе всегда останется хотя бы один админ. */
create function public.admin_set_admin(p_user uuid, p_on boolean, p_note text default '') returns void language plpgsql security definer set search_path = ''
as $$
begin
  perform private.need_admin();
  if not exists (select 1 from auth.users where id = p_user) then raise exception 'Человек не найден'; end if;
  if p_on then
    if private.phone_of((select email from auth.users where id = p_user)) is not null then
      raise exception 'Админ входит по почте и паролю. Учётная запись по номеру телефона не годится: вход по номеру пока без SMS';
    end if;
    insert into private.admins (user_id, note, added_by) values (p_user, left(coalesce(p_note, ''), 100), auth.uid())
    on conflict (user_id) do update set active = true, note = excluded.note, added_at = now(), added_by = auth.uid();
  else
    if p_user = auth.uid() then raise exception 'Себя снять нельзя — попросите другого админа'; end if;
    update private.admins set active = false where user_id = p_user;
  end if;
  perform private.log(case when p_on then 'admin_add' else 'admin_remove' end, 'admin', p_user::text, p_note);
end;
$$;

-- ---------- права ----------
-- служебные функции — только для функций выше
revoke execute on function private.guard_blocked(), private.guard_shop_owner(), private.guard_new_order(), private.guard_review(),
  private.is_admin(), private.need_admin(), private.log(text, text, text, text, jsonb), private.phone_of(text), private.roles_of(uuid, text),
  private.name_of(uuid, text), private.uinfo(uuid), private.order_row(public.orders) from public, anon, authenticated;
-- функции админа: вызвать может любой вошедший, но каждая сама проверяет, что это админ (иначе «Нет доступа»)
revoke execute on function public.admin_me(), public.admin_overview(), public.admin_users(text, text), public.admin_user(uuid),
  public.admin_shops(text), public.admin_shop(uuid), public.admin_products(text, text), public.admin_orders(text, text, uuid, uuid, date, date),
  public.admin_order(text), public.admin_couriers(), public.admin_map(), public.admin_reviews(text), public.admin_checks(), public.admin_log(integer),
  public.admin_system(), public.admin_shop_block(uuid, boolean, text), public.admin_product_block(text, boolean, text),
  public.admin_courier_block(uuid, boolean, text), public.admin_user_block(uuid, boolean, text), public.admin_order_cancel(text, text),
  public.admin_order_release(text, text), public.admin_order_delivered(text, text), public.admin_order_resolve(text, text),
  public.admin_review_decide(uuid, boolean, text), public.admin_set_admin(uuid, boolean, text) from public, anon;
grant execute on function public.admin_me(), public.admin_overview(), public.admin_users(text, text), public.admin_user(uuid),
  public.admin_shops(text), public.admin_shop(uuid), public.admin_products(text, text), public.admin_orders(text, text, uuid, uuid, date, date),
  public.admin_order(text), public.admin_couriers(), public.admin_map(), public.admin_reviews(text), public.admin_checks(), public.admin_log(integer),
  public.admin_system(), public.admin_shop_block(uuid, boolean, text), public.admin_product_block(text, boolean, text),
  public.admin_courier_block(uuid, boolean, text), public.admin_user_block(uuid, boolean, text), public.admin_order_cancel(text, text),
  public.admin_order_release(text, text), public.admin_order_delivered(text, text), public.admin_order_resolve(text, text),
  public.admin_review_decide(uuid, boolean, text), public.admin_set_admin(uuid, boolean, text) to authenticated;

-- ПЕРВЫЙ АДМИН (один раз, вручную — не из приложения):
--   1. Supabase → Authentication → Users → Add user → Create new user: ваша почта и длинный пароль, галочка «Auto Confirm User».
--   2. Supabase → SQL Editor:
--        insert into private.admins (user_id, note) select id, 'владелец' from auth.users where email = 'ваша@почта';
-- Следующих админов первый добавляет в панели: «Люди» → человек → «Сделать админом».
