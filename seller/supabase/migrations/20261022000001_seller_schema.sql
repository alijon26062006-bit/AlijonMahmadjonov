-- Кабинет продавца: магазины, товары, заказы, расходы.
-- Правило доступа одно: продавец видит и меняет только строки своего магазина.

-- ---------- магазин ----------
create table public.shops (
  id            uuid primary key default gen_random_uuid(),
  owner_id      uuid not null unique default auth.uid() references auth.users (id) on delete cascade,
  name          text not null check (char_length(name) between 1 and 60),
  type          text not null,
  phone         text not null,
  address       text not null,
  about         text not null default '',
  logo_url      text,
  paused        boolean not null default false,
  min_order     numeric(12, 2) not null default 0 check (min_order >= 0),
  delivery      boolean not null default true,
  pickup        boolean not null default true,
  prep_min      integer not null default 30 check (prep_min between 1 and 600),
  schedule      jsonb not null default '[]'::jsonb,
  alif_terminal text check (alif_terminal ~ '^\d{6,}$'),
  alif_holder   text,
  alif_tin      text,
  alif_status   text not null default 'none' check (alif_status in ('none', 'pending', 'connected')),
  created_at    timestamptz not null default now()
);

-- принадлежит ли магазин текущему пользователю; используется во всех политиках ниже
create function public.owns_shop(p_shop_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (select 1 from public.shops s where s.id = p_shop_id and s.owner_id = (select auth.uid()));
$$;
revoke execute on function public.owns_shop(uuid) from public, anon;
grant execute on function public.owns_shop(uuid) to authenticated;

-- ---------- каталог ----------
create table public.categories (
  id       uuid primary key default gen_random_uuid(),
  shop_id  uuid not null references public.shops (id) on delete cascade,
  name     text not null check (char_length(name) between 1 and 30),
  position integer not null default 0,
  unique (shop_id, name)
);

create table public.products (
  id          uuid primary key default gen_random_uuid(),
  shop_id     uuid not null references public.shops (id) on delete cascade,
  category_id uuid references public.categories (id) on delete set null,
  name        text not null check (char_length(name) between 1 and 80),
  description text not null default '',
  price       numeric(12, 2) not null check (price > 0),
  old_price   numeric(12, 2) check (old_price is null or old_price > price),
  cost        numeric(12, 2) check (cost is null or cost >= 0),
  stock       integer not null default 0 check (stock >= 0),
  unit        text not null default 'шт',
  labels      text[] not null default '{}',
  prep_min    integer check (prep_min is null or prep_min between 1 and 600),
  images      text[] not null default '{}' check (cardinality(images) <= 4),
  active      boolean not null default true,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table public.product_variants (
  id         uuid primary key default gen_random_uuid(),
  product_id uuid not null references public.products (id) on delete cascade,
  name       text not null check (char_length(name) between 1 and 40),
  price      numeric(12, 2) not null check (price > 0),
  cost       numeric(12, 2) check (cost is null or cost >= 0),
  position   integer not null default 0
);

-- ---------- заказы ----------
-- номер заказа сквозной и человекочитаемый: 1001, 1002, ...
create table public.orders (
  id             uuid primary key default gen_random_uuid(),
  number         bigint generated always as identity (start with 1001) unique,
  shop_id        uuid not null references public.shops (id) on delete cascade,
  source         text not null check (source in ('app', 'shop')),
  status         text not null default 'new' check (status in ('new', 'accepted', 'ready', 'done', 'cancelled')),
  delivery       text not null default 'courier' check (delivery in ('courier', 'pickup', 'shop')),
  customer_name  text,
  customer_phone text,
  address        text,
  comment        text not null default '',
  pay            text not null default 'cash',
  ready_in_min   integer,
  cancel_reason  text,
  created_at     timestamptz not null default now(),
  accepted_at    timestamptz,
  completed_at   timestamptz
);

create table public.order_items (
  id         uuid primary key default gen_random_uuid(),
  order_id   uuid not null references public.orders (id) on delete cascade,
  product_id uuid references public.products (id) on delete set null,
  name       text not null,
  variant    text not null default '',
  qty        integer not null check (qty > 0),
  price      numeric(12, 2) not null check (price >= 0),
  cost       numeric(12, 2)
);

-- ---------- расходы ----------
create table public.expenses (
  id             uuid primary key default gen_random_uuid(),
  shop_id        uuid not null references public.shops (id) on delete cascade,
  spent_on       date not null default current_date,
  category       text not null,
  amount         numeric(12, 2) not null check (amount > 0),
  note           text not null default '',
  stock_purchase boolean not null default false,
  created_at     timestamptz not null default now()
);

-- ---------- индексы под частые запросы ----------
create index categories_shop_idx       on public.categories (shop_id);
create index products_shop_idx         on public.products (shop_id);
create index products_category_idx     on public.products (category_id);
create index product_variants_prod_idx on public.product_variants (product_id);
create index orders_shop_created_idx   on public.orders (shop_id, created_at desc);
create index order_items_order_idx     on public.order_items (order_id);
create index order_items_product_idx   on public.order_items (product_id);
create index expenses_shop_date_idx    on public.expenses (shop_id, spent_on desc);

-- updated_at у товара
create function public.touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;
create trigger products_touch before update on public.products
  for each row execute function public.touch_updated_at();

-- ---------- доступ ----------
alter table public.shops            enable row level security;
alter table public.categories       enable row level security;
alter table public.products         enable row level security;
alter table public.product_variants enable row level security;
alter table public.orders           enable row level security;
alter table public.order_items      enable row level security;
alter table public.expenses         enable row level security;

create policy "Владелец управляет своим магазином" on public.shops
  for all to authenticated
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

create policy "Владелец управляет категориями" on public.categories
  for all to authenticated
  using (public.owns_shop(shop_id)) with check (public.owns_shop(shop_id));

create policy "Владелец управляет товарами" on public.products
  for all to authenticated
  using (public.owns_shop(shop_id)) with check (public.owns_shop(shop_id));

create policy "Владелец управляет вариантами" on public.product_variants
  for all to authenticated
  using (exists (select 1 from public.products p where p.id = product_id and public.owns_shop(p.shop_id)))
  with check (exists (select 1 from public.products p where p.id = product_id and public.owns_shop(p.shop_id)));

-- заказы из приложения создаёт сервер; продавец видит свои заказы, меняет статус и сам записывает продажи в магазине
create policy "Владелец видит свои заказы" on public.orders
  for select to authenticated using (public.owns_shop(shop_id));
create policy "Владелец записывает продажу в магазине" on public.orders
  for insert to authenticated with check (public.owns_shop(shop_id) and source = 'shop');
create policy "Владелец меняет статус своих заказов" on public.orders
  for update to authenticated using (public.owns_shop(shop_id)) with check (public.owns_shop(shop_id));

create policy "Владелец видит позиции своих заказов" on public.order_items
  for select to authenticated
  using (exists (select 1 from public.orders o where o.id = order_id and public.owns_shop(o.shop_id)));
create policy "Владелец добавляет позиции продажи в магазине" on public.order_items
  for insert to authenticated
  with check (exists (select 1 from public.orders o where o.id = order_id and o.source = 'shop' and public.owns_shop(o.shop_id)));

create policy "Владелец управляет расходами" on public.expenses
  for all to authenticated
  using (public.owns_shop(shop_id)) with check (public.owns_shop(shop_id));
