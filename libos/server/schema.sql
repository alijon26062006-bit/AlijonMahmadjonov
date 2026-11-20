-- ISTANBUL bonus program: database for the cashier app and the customer app.
-- Tables are closed to the public API. Apps call only the functions below;
-- every call after login carries a session token.

create extension if not exists pgcrypto with schema extensions;

create table public.settings (
  id int primary key default 1 check (id = 1),
  store_name text not null default 'ISTANBUL',
  welcome_bonus int not null default 1000,
  max_spend_pct int not null default 50,
  levels jsonb not null default '[{"name":"Базовый","pct":3,"from":0},{"name":"Серебро","pct":5,"from":100000},{"name":"Золото","pct":7,"from":250000}]'
);
insert into public.settings default values;

create table public.cashiers (
  id bigint generated always as identity primary key,
  name text not null,
  pin_hash text not null,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table public.customers (
  id bigint generated always as identity primary key,
  phone text not null unique check (phone ~ '^[0-9]{10}$'),
  first_name text not null,
  last_name text not null default '',
  balance int not null default 0 check (balance >= 0),
  in_rating boolean not null default true,
  login_hash text,
  redeem_code text,
  redeem_until timestamptz,
  redeem_tries int not null default 0,
  created_by bigint references public.cashiers(id),
  created_at timestamptz not null default now()
);

create table public.shifts (
  id bigint generated always as identity primary key,
  cashier_id bigint not null references public.cashiers(id),
  opened_at timestamptz not null default now(),
  closed_at timestamptz
);

create table public.operations (
  id bigint generated always as identity primary key,
  customer_id bigint not null references public.customers(id),
  cashier_id bigint references public.cashiers(id),
  shift_id bigint references public.shifts(id),
  kind text not null check (kind in ('sale', 'refund', 'welcome')),
  amount int not null default 0,
  spend int not null default 0,
  pay int not null default 0,
  earn int not null default 0,
  ref_id bigint references public.operations(id),
  refunded boolean not null default false,
  client_key uuid unique,
  created_at timestamptz not null default now()
);
create index operations_customer_idx on public.operations (customer_id, created_at desc);
create index operations_shift_idx on public.operations (shift_id);
create index operations_created_idx on public.operations (created_at);
create index operations_ref_idx on public.operations (ref_id);
create index customers_created_by_idx on public.customers (created_by);
create index shifts_cashier_idx on public.shifts (cashier_id);
create index operations_cashier_idx on public.operations (cashier_id);

create table public.sessions (
  token uuid primary key default gen_random_uuid(),
  kind text not null check (kind in ('cashier', 'customer')),
  subject_id bigint not null,
  shift_id bigint,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);
create index sessions_shift_idx on public.sessions (shift_id);

create table public.login_failures (
  id bigint generated always as identity primary key,
  kind text not null,
  key text not null,
  created_at timestamptz not null default now()
);
create index login_failures_idx on public.login_failures (kind, key, created_at);

alter table public.settings enable row level security;
alter table public.cashiers enable row level security;
alter table public.customers enable row level security;
alter table public.shifts enable row level security;
alter table public.operations enable row level security;
alter table public.sessions enable row level security;
alter table public.login_failures enable row level security;
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;

-- ---------- helpers (not callable from the apps) ----------

create function public._err(p_code text) returns jsonb language sql immutable as $$
  select jsonb_build_object('error', p_code)
$$;

create function public._digits(n int) returns text
language sql volatile security definer set search_path = public, extensions as $$
  select string_agg((get_byte(b, i) % 10)::text, '' order by i) from (select gen_random_bytes(n) as b) x, generate_series(0, n - 1) i
$$;

create function public._session(p_token uuid, p_kind text) returns public.sessions
language sql stable security definer set search_path = public as $$
  select * from sessions where token = p_token and kind = p_kind and expires_at > now()
$$;

create function public._month_start() returns timestamptz language sql stable as $$
  select date_trunc('month', now() at time zone 'Asia/Almaty') at time zone 'Asia/Almaty'
$$;

create function public._short(p_first text, p_last text) returns text language sql immutable as $$
  select p_first || case when coalesce(p_last, '') = '' then '' else ' ' || left(p_last, 1) || '.' end
$$;

create function public._level(p_total int) returns jsonb
language sql stable security definer set search_path = public as $$
  with l as (select e, ord from settings, jsonb_array_elements(levels) with ordinality as t(e, ord)),
  cur as (select e, ord from l where (e->>'from')::int <= p_total order by ord desc limit 1),
  nxt as (select e from l where (e->>'from')::int > p_total order by ord limit 1)
  select jsonb_build_object(
    'idx', (select ord from cur) - 1, 'name', (select e->>'name' from cur), 'pct', (select (e->>'pct')::int from cur),
    'next_name', (select e->>'name' from nxt), 'next_from', (select (e->>'from')::int from nxt))
$$;

create function public._year_total(p_id bigint) returns int
language sql stable security definer set search_path = public as $$
  select coalesce(sum(amount), 0)::int from operations
  where customer_id = p_id and kind = 'sale' and not refunded and created_at > now() - interval '365 days'
$$;

create function public._rating(p_me bigint) returns jsonb
language sql stable security definer set search_path = public as $$
  with s as (
    select c.id, c.first_name, c.last_name, sum(o.amount)::int as score
    from operations o join customers c on c.id = o.customer_id
    where o.kind = 'sale' and not o.refunded and o.created_at >= _month_start() and c.in_rating
    group by c.id),
  r as (select s.*, row_number() over (order by score desc, id) as place from s)
  select jsonb_build_object(
    'top', coalesce((select jsonb_agg(jsonb_build_object('place', place, 'name', _short(first_name, last_name),
      'initials', upper(left(first_name, 1) || left(coalesce(last_name, ''), 1)), 'score', score, 'me', id = p_me) order by place)
      from r where place <= 10), '[]'::jsonb),
    'me', (select jsonb_build_object('place', place, 'score', score) from r where id = p_me),
    'above', (select jsonb_build_object('place', a.place, 'name', _short(a.first_name, a.last_name), 'score', a.score)
      from r a where a.place = coalesce((select place - 1 from r where id = p_me), (select max(place) from r))),
    'scorers', (select count(*) from r),
    'members', (select count(*) from customers where in_rating),
    'month_start', _month_start())
$$;

create function public._customer(p_id bigint) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare c customers; yt int; rt jsonb;
begin
  select * into c from customers where id = p_id;
  if not found then return null; end if;
  yt := _year_total(p_id);
  rt := _rating(p_id);
  return jsonb_build_object('id', c.id, 'phone', c.phone, 'first_name', c.first_name, 'last_name', c.last_name,
    'balance', c.balance, 'year_total', yt, 'level', _level(yt), 'in_rating', c.in_rating,
    'visits', (select count(*) from operations where customer_id = p_id and kind = 'sale' and not refunded),
    'place', case when c.in_rating then coalesce((rt->'me'->>'place')::int, (rt->>'scorers')::int + 1) end,
    'month_score', coalesce((rt->'me'->>'score')::int, 0), 'created_at', c.created_at);
end $$;

create function public._ops(p_customer bigint, p_shift bigint, p_limit int) returns jsonb
language sql stable security definer set search_path = public as $$
  select coalesce(jsonb_agg(to_jsonb(x) order by x.id desc), '[]'::jsonb) from (
    select o.id, o.kind, o.amount, o.spend, o.pay, o.earn, o.refunded, o.ref_id, o.created_at,
      c.id as customer_id, c.first_name, c.last_name
    from operations o join customers c on c.id = o.customer_id
    where (p_customer is null or o.customer_id = p_customer) and (p_shift is null or o.shift_id = p_shift)
    order by o.id desc limit p_limit) x
$$;

create function public._shift_stats(p_shift bigint) returns jsonb
language sql stable security definer set search_path = public as $$
  select jsonb_build_object(
    'id', sh.id, 'opened_at', sh.opened_at, 'closed_at', sh.closed_at, 'cashier', ca.name,
    'cnt', count(o.id) filter (where o.kind = 'sale'),
    'gross', coalesce(sum(o.pay) filter (where o.kind = 'sale'), 0),
    'revenue', coalesce(sum(o.pay) filter (where o.kind = 'sale'), 0) - coalesce(sum(o.pay) filter (where o.kind = 'refund'), 0),
    'earn', coalesce(sum(o.earn) filter (where o.kind in ('sale', 'welcome')), 0) - coalesce(sum(o.earn) filter (where o.kind = 'refund'), 0),
    'spend', coalesce(sum(o.spend) filter (where o.kind = 'sale'), 0) - coalesce(sum(o.spend) filter (where o.kind = 'refund'), 0),
    'news', count(o.id) filter (where o.kind = 'welcome'),
    'refunds', count(o.id) filter (where o.kind = 'refund'),
    'hours', (select coalesce(jsonb_object_agg(h, v), '{}'::jsonb) from (
      select extract(hour from o2.created_at at time zone 'Asia/Almaty')::int as h, sum(o2.pay)::int as v
      from operations o2 where o2.shift_id = sh.id and o2.kind = 'sale' group by 1) x))
  from shifts sh join cashiers ca on ca.id = sh.cashier_id left join operations o on o.shift_id = sh.id
  where sh.id = p_shift
  group by sh.id, ca.name
$$;

-- ---------- public: both apps ----------

create function public.app_settings() returns jsonb
language sql stable security definer set search_path = public as $$
  select jsonb_build_object('store_name', store_name, 'welcome_bonus', welcome_bonus, 'max_spend_pct', max_spend_pct, 'levels', levels) from settings
$$;

-- ---------- cashier app ----------

create function public.cashier_login(p_pin text) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare c cashiers; sh shifts; tok uuid;
begin
  if (select count(*) from login_failures where kind = 'cashier' and created_at > now() - interval '15 minutes') >= 10 then
    return _err('locked');
  end if;
  select * into c from cashiers where active and pin_hash = crypt(coalesce(p_pin, ''), pin_hash) limit 1;
  if not found then
    insert into login_failures (kind, key) values ('cashier', '*');
    return _err('pin');
  end if;
  select * into sh from shifts where cashier_id = c.id and closed_at is null order by id desc limit 1;
  if found and sh.opened_at < now() - interval '20 hours' then
    update shifts set closed_at = now() where id = sh.id;
    delete from sessions where shift_id = sh.id;
    sh := null;
  end if;
  if sh.id is null then
    insert into shifts (cashier_id) values (c.id) returning * into sh;
  end if;
  insert into sessions (kind, subject_id, shift_id, expires_at) values ('cashier', c.id, sh.id, now() + interval '16 hours') returning token into tok;
  return jsonb_build_object('token', tok, 'name', c.name, 'settings', app_settings(), 'shift', _shift_stats(sh.id));
end $$;

create function public.cashier_me(p_token uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare s sessions; c cashiers;
begin
  s := _session(p_token, 'cashier'); if s.token is null then return _err('auth'); end if;
  select * into c from cashiers where id = s.subject_id;
  return jsonb_build_object('name', c.name, 'settings', app_settings(), 'shift', _shift_stats(s.shift_id), 'ops', _ops(null, s.shift_id, 200));
end $$;

create function public.cashier_logout(p_token uuid) returns jsonb
language sql security definer set search_path = public as $$
  delete from sessions where token = p_token and kind = 'cashier';
  select jsonb_build_object('ok', true)
$$;

create function public.cashier_find(p_token uuid, p_q text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare s sessions; q text := regexp_replace(coalesce(p_q, ''), '\D', '', 'g');
begin
  s := _session(p_token, 'cashier'); if s.token is null then return _err('auth'); end if;
  if length(q) < 2 then return jsonb_build_object('list', '[]'::jsonb); end if;
  return jsonb_build_object('list', coalesce((select jsonb_agg(jsonb_build_object('id', id, 'phone', phone, 'first_name', first_name,
      'last_name', last_name, 'balance', balance) order by first_name)
    from (select * from customers where phone like q || '%' or (length(q) >= 4 and phone like '%' || q) limit 20) x), '[]'::jsonb));
end $$;

create function public.cashier_customer(p_token uuid, p_id bigint, p_phone text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare s sessions; cid bigint;
begin
  s := _session(p_token, 'cashier'); if s.token is null then return _err('auth'); end if;
  select id into cid from customers where id = p_id or phone = p_phone limit 1;
  if cid is null then return _err('not_found'); end if;
  return jsonb_build_object('customer', _customer(cid), 'ops', _ops(cid, null, 30));
end $$;

create function public.cashier_register(p_token uuid, p_phone text, p_first text, p_last text) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare s sessions; st settings; c customers; code text; ph text := regexp_replace(coalesce(p_phone, ''), '\D', '', 'g');
begin
  s := _session(p_token, 'cashier'); if s.token is null then return _err('auth'); end if;
  if ph !~ '^[0-9]{10}$' then return _err('phone'); end if;
  if length(trim(coalesce(p_first, ''))) < 2 then return _err('name'); end if;
  select * into c from customers where phone = ph;
  if found then return jsonb_build_object('error', 'exists', 'customer_id', c.id); end if;
  select * into st from settings;
  code := _digits(6);
  insert into customers (phone, first_name, last_name, balance, login_hash, created_by)
    values (ph, left(trim(p_first), 40), left(trim(coalesce(p_last, '')), 40), st.welcome_bonus, crypt(code, gen_salt('bf', 6)), s.subject_id)
    returning * into c;
  insert into operations (customer_id, cashier_id, shift_id, kind, earn) values (c.id, s.subject_id, s.shift_id, 'welcome', st.welcome_bonus);
  return jsonb_build_object('customer', _customer(c.id), 'ops', _ops(c.id, null, 30), 'login_code', code);
end $$;

create function public.cashier_new_code(p_token uuid, p_id bigint) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare s sessions; code text;
begin
  s := _session(p_token, 'cashier'); if s.token is null then return _err('auth'); end if;
  code := _digits(6);
  update customers set login_hash = crypt(code, gen_salt('bf', 6)) where id = p_id;
  if not found then return _err('not_found'); end if;
  return jsonb_build_object('login_code', code);
end $$;

create function public.cashier_sale(p_token uuid, p_customer bigint, p_amount int, p_spend int, p_code text, p_key uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare s sessions; c customers; st settings; yt int; lv jsonb; lv2 jsonb; mx int; v_pay int; v_earn int; o operations; bal0 int; sp int := coalesce(p_spend, 0);
begin
  s := _session(p_token, 'cashier'); if s.token is null then return _err('auth'); end if;
  if p_key is not null then
    select * into o from operations where client_key = p_key;
    if found then return jsonb_build_object('op', to_jsonb(o), 'customer', _customer(o.customer_id), 'repeat', true); end if;
  end if;
  if p_amount is null or p_amount < 1 or p_amount > 100000000 then return _err('amount'); end if;
  if sp < 0 then return _err('spend'); end if;
  select * into c from customers where id = p_customer for update;
  if not found then return _err('not_found'); end if;
  select * into st from settings;
  yt := _year_total(c.id);
  lv := _level(yt);
  mx := least(c.balance, floor(p_amount * st.max_spend_pct / 100.0)::int);
  if sp > mx then return _err('spend'); end if;
  if sp > 0 then
    if c.redeem_code is null or c.redeem_until < now() or c.redeem_tries >= 3 then return _err('code_expired'); end if;
    if p_code is distinct from c.redeem_code then
      update customers set redeem_tries = redeem_tries + 1 where id = c.id;
      return _err('code');
    end if;
    update customers set redeem_code = null, redeem_until = null, redeem_tries = 0 where id = c.id;
  end if;
  v_pay := p_amount - sp;
  v_earn := round(v_pay * (lv->>'pct')::int / 100.0)::int;
  bal0 := c.balance;
  update customers set balance = balance - sp + v_earn where id = c.id;
  insert into operations (customer_id, cashier_id, shift_id, kind, amount, spend, pay, earn, client_key)
    values (c.id, s.subject_id, s.shift_id, 'sale', p_amount, sp, v_pay, v_earn, p_key) returning * into o;
  lv2 := _level(yt + p_amount);
  return jsonb_build_object('op', to_jsonb(o), 'customer', _customer(c.id), 'balance_before', bal0, 'pct', (lv->>'pct')::int,
    'level_up', case when (lv2->>'idx')::int > (lv->>'idx')::int then lv2 end);
end $$;

create function public.cashier_refund(p_token uuid, p_op bigint) returns jsonb
language plpgsql security definer set search_path = public as $$
declare s sessions; o operations; r operations;
begin
  s := _session(p_token, 'cashier'); if s.token is null then return _err('auth'); end if;
  select * into o from operations where id = p_op and kind = 'sale' for update;
  if not found then return _err('not_found'); end if;
  if o.refunded then return _err('refunded'); end if;
  perform 1 from customers where id = o.customer_id for update;
  update customers set balance = greatest(0, balance - o.earn + o.spend) where id = o.customer_id;
  update operations set refunded = true where id = o.id;
  insert into operations (customer_id, cashier_id, shift_id, kind, amount, spend, pay, earn, ref_id)
    values (o.customer_id, s.subject_id, s.shift_id, 'refund', o.amount, o.spend, o.pay, o.earn, o.id) returning * into r;
  return jsonb_build_object('op', to_jsonb(r), 'customer', _customer(o.customer_id), 'ops', _ops(o.customer_id, null, 30));
end $$;

create function public.cashier_close_shift(p_token uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare s sessions;
begin
  s := _session(p_token, 'cashier'); if s.token is null then return _err('auth'); end if;
  update shifts set closed_at = now() where id = s.shift_id and closed_at is null;
  delete from sessions where shift_id = s.shift_id;
  return jsonb_build_object('shift', _shift_stats(s.shift_id));
end $$;

-- ---------- customer app ----------

create function public.customer_login(p_phone text, p_code text) returns jsonb
language plpgsql security definer set search_path = public, extensions as $$
declare c customers; tok uuid; ph text := regexp_replace(coalesce(p_phone, ''), '\D', '', 'g');
begin
  if (select count(*) from login_failures where kind = 'customer' and key = ph and created_at > now() - interval '15 minutes') >= 5 then
    return _err('locked');
  end if;
  select * into c from customers where phone = ph;
  if not found or c.login_hash is null or c.login_hash <> crypt(coalesce(p_code, ''), c.login_hash) then
    insert into login_failures (kind, key) values ('customer', ph);
    return _err('code');
  end if;
  insert into sessions (kind, subject_id, expires_at) values ('customer', c.id, now() + interval '180 days') returning token into tok;
  return jsonb_build_object('token', tok);
end $$;

create function public.customer_me(p_token uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare s sessions;
begin
  s := _session(p_token, 'customer'); if s.token is null then return _err('auth'); end if;
  return jsonb_build_object('customer', _customer(s.subject_id), 'ops', _ops(s.subject_id, null, 100),
    'rating', _rating(s.subject_id), 'settings', app_settings());
end $$;

create function public.customer_redeem_code(p_token uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare s sessions; code text := _digits(4);
begin
  s := _session(p_token, 'customer'); if s.token is null then return _err('auth'); end if;
  update customers set redeem_code = code, redeem_until = now() + interval '10 minutes', redeem_tries = 0 where id = s.subject_id;
  return jsonb_build_object('code', code, 'seconds', 600);
end $$;

create function public.customer_settings(p_token uuid, p_in_rating boolean) returns jsonb
language plpgsql security definer set search_path = public as $$
declare s sessions;
begin
  s := _session(p_token, 'customer'); if s.token is null then return _err('auth'); end if;
  update customers set in_rating = coalesce(p_in_rating, in_rating) where id = s.subject_id;
  return jsonb_build_object('ok', true);
end $$;

create function public.customer_logout(p_token uuid) returns jsonb
language sql security definer set search_path = public as $$
  delete from sessions where token = p_token and kind = 'customer';
  select jsonb_build_object('ok', true)
$$;

-- ---------- who may call what ----------

revoke execute on all functions in schema public from public, anon, authenticated;
grant execute on function
  public.app_settings(),
  public.cashier_login(text), public.cashier_me(uuid), public.cashier_logout(uuid), public.cashier_find(uuid, text),
  public.cashier_customer(uuid, bigint, text), public.cashier_register(uuid, text, text, text), public.cashier_new_code(uuid, bigint),
  public.cashier_sale(uuid, bigint, int, int, text, uuid), public.cashier_refund(uuid, bigint), public.cashier_close_shift(uuid),
  public.customer_login(text, text), public.customer_me(uuid), public.customer_redeem_code(uuid), public.customer_settings(uuid, boolean),
  public.customer_logout(uuid)
to anon, authenticated;
