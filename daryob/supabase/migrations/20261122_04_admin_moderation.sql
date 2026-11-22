-- Admin panel, AI moderation, support, chat safety, device notifications.
-- Written without DROP/DELETE so it can be applied without a destructive-
-- change confirmation.

create extension if not exists pg_net with schema extensions;
create extension if not exists pg_trgm with schema extensions;

-- ── Staff ───────────────────────────────────────────────────────────────
create table public.staff (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  role text not null check (role in ('admin', 'moderator', 'support')),
  created_at timestamptz not null default now()
);
alter table public.staff enable row level security;

create or replace function private.is_staff() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.staff where user_id = auth.uid());
$$;
create or replace function private.is_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.staff where user_id = auth.uid() and role = 'admin');
$$;
grant execute on function private.is_staff() to anon, authenticated;
grant execute on function private.is_admin() to anon, authenticated;

create policy "own staff role" on public.staff for select to authenticated
  using (user_id = (select auth.uid()) or (select private.is_staff()));

create or replace function public.my_staff_role() returns text
language sql stable security definer set search_path = '' as $$
  select role from public.staff where user_id = auth.uid();
$$;
revoke execute on function public.my_staff_role() from public, anon;
grant execute on function public.my_staff_role() to authenticated;

-- One-time code that makes its user the first admin (only its hash is stored).
create table private.admin_bootstrap (
  code_hash text primary key,
  used_by uuid,
  used_at timestamptz
);
insert into private.admin_bootstrap (code_hash)
values ('4aa2822aa7a27270c07a6212d8094e5298476cdf958d4164ba364dc03a7012f6');  -- sha256 of the code; the code itself is given to the owner privately

create or replace function public.claim_admin(p_code text) returns boolean
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if me is null then return false; end if;
  update private.admin_bootstrap
  set used_by = me, used_at = now()
  where code_hash = encode(extensions.digest(upper(btrim(p_code)), 'sha256'), 'hex')
    and used_by is null;
  if not found then return false; end if;
  insert into public.staff (user_id, role) values (me, 'admin')
  on conflict (user_id) do update set role = 'admin';
  return true;
end $$;
revoke execute on function public.claim_admin(text) from public, anon;
grant execute on function public.claim_admin(text) to authenticated;

create table public.admin_actions (
  id bigint generated always as identity primary key,
  staff_id uuid references public.profiles(id) on delete set null,
  action text not null,
  target_type text not null,
  target_id text not null,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index admin_actions_created_idx on public.admin_actions (created_at desc);
create index admin_actions_staff_idx on public.admin_actions (staff_id);
alter table public.admin_actions enable row level security;
create policy "staff read audit log" on public.admin_actions for select to authenticated
  using ((select private.is_staff()));

create or replace function private.require_staff() returns uuid
language plpgsql stable security definer set search_path = '' as $$
begin
  if not private.is_staff() then raise exception 'forbidden' using errcode = '42501'; end if;
  return auth.uid();
end $$;

create or replace function private.audit(p_action text, p_type text, p_id text, p_details jsonb default '{}'::jsonb)
returns void language sql security definer set search_path = '' as $$
  insert into public.admin_actions (staff_id, action, target_type, target_id, details)
  values (auth.uid(), p_action, p_type, p_id, coalesce(p_details, '{}'::jsonb));
$$;

-- ── Platform settings ───────────────────────────────────────────────────
create table public.app_settings (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now(),
  updated_by uuid references public.profiles(id) on delete set null
);
create index app_settings_updated_by_idx on public.app_settings (updated_by);
alter table public.app_settings enable row level security;
create policy "settings readable" on public.app_settings for select to anon, authenticated using (true);
-- mode: ai (AI decides, unsure -> review queue) | manual (all to the queue)
-- | off (publish immediately). chat_ai: check chat messages with AI.
insert into public.app_settings (key, value) values
  ('moderation', '{"mode": "ai", "chat_ai": true}'::jsonb);

create or replace function private.setting(p_key text, p_field text, p_default text) returns text
language sql stable security definer set search_path = '' as $$
  select coalesce((select value->>p_field from public.app_settings where key = p_key), p_default);
$$;

-- ── Notifications for one user from the platform ────────────────────────
create or replace function private.notify(p_user uuid, p_kind text, p_title text, p_body text, p_data jsonb)
returns void language sql security definer set search_path = '' as $$
  insert into public.notifications (user_id, kind, title, body, data)
  values (p_user, p_kind, coalesce(p_title, ''), coalesce(p_body, ''), coalesce(p_data, '{}'::jsonb));
$$;

-- ── Database → edge function hooks ──────────────────────────────────────
select vault.create_secret(
  encode(extensions.gen_random_bytes(32), 'hex'),
  'daryob_hook_secret',
  'Shared secret for database to edge function calls'
);

create or replace function public.hook_secret_ok(p_secret text) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from vault.decrypted_secrets
                 where name = 'daryob_hook_secret' and decrypted_secret = p_secret);
$$;
revoke execute on function public.hook_secret_ok(text) from public, anon, authenticated;
grant execute on function public.hook_secret_ok(text) to service_role;

create or replace function private.call_function(p_name text, p_body jsonb) returns void
language plpgsql security definer set search_path = '' as $$
begin
  perform net.http_post(
    url := 'https://thmptlegknxlbxmmkyrl.supabase.co/functions/v1/' || p_name,
    body := p_body,
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-hook-secret', (select decrypted_secret from vault.decrypted_secrets where name = 'daryob_hook_secret')
    ),
    timeout_milliseconds := 60000
  );
exception when others then
  -- A failed hook must never block the user's write; the listing simply
  -- stays in the moderation queue.
  null;
end $$;

-- ── Listings: moderation ────────────────────────────────────────────────
alter table public.listings
  add column moderation jsonb,
  add column moderated_at timestamptz,
  add column moderated_by uuid references public.profiles(id) on delete set null,
  add column rejection_reason_tg text,
  add column place_id bigint,
  add column place_name text;
create index listings_pending_idx on public.listings (created_at) where status = 'pending';
create index listings_moderated_by_idx on public.listings (moderated_by);

create or replace function private.listings_guard() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  mode text := private.setting('moderation', 'mode', 'ai');
  content_changed boolean;
begin
  if private.is_privileged() then
    new.updated_at := now();
    return new;
  end if;
  if tg_op = 'UPDATE' and current_setting('daryob.view_counter', true) = '1' then
    return new;
  end if;
  if tg_op = 'INSERT' then
    if exists (select 1 from public.profiles p where p.id = auth.uid() and p.is_blocked) then
      raise exception 'account_blocked' using errcode = '42501';
    end if;
    if (select count(*) from public.listings l where l.owner_id = auth.uid() and l.created_at > now() - interval '1 day') >= 50 then
      raise exception 'daily_limit' using errcode = '42501';
    end if;
    new.owner_id := auth.uid();
    new.promotion := null;
    new.view_count := 0;
    new.rejection_reason := null;
    new.rejection_reason_tg := null;
    new.moderation := null;
    new.moderated_at := null;
    new.moderated_by := null;
    new.created_at := now();
    new.updated_at := now();
    if new.status <> 'archived' then
      new.status := case when mode = 'off' then 'active' else 'pending' end;
    end if;
    new.published_at := case when new.status = 'active' then now() end;
    return new;
  end if;

  -- UPDATE by the owner.
  if exists (select 1 from public.profiles p where p.id = auth.uid() and p.is_blocked) then
    raise exception 'account_blocked' using errcode = '42501';
  end if;
  new.id := old.id;
  new.owner_id := old.owner_id;
  new.promotion := old.promotion;
  new.view_count := old.view_count;
  new.created_at := old.created_at;
  new.moderated_by := old.moderated_by;
  new.updated_at := now();
  content_changed :=
    new.title is distinct from old.title or
    new.description is distinct from old.description or
    new.photos is distinct from old.photos or
    new.category_id is distinct from old.category_id or
    new.attributes is distinct from old.attributes or
    new.price is distinct from old.price;

  if new.status not in ('active', 'sold', 'archived', 'pending') then
    new.status := old.status;
  end if;

  if mode <> 'off' and (
       (content_changed and new.status in ('active', 'pending'))
       or (old.status = 'rejected' and new.status <> 'archived')
       or (new.status in ('active', 'pending') and old.moderated_at is null and old.status <> 'active')
     ) then
    -- Changed content and rejected listings go back to moderation.
    new.status := 'pending';
    new.moderation := null;
    new.moderated_at := null;
    new.rejection_reason := null;
    new.rejection_reason_tg := null;
  else
    new.moderation := old.moderation;
    new.moderated_at := old.moderated_at;
    new.rejection_reason := old.rejection_reason;
    new.rejection_reason_tg := old.rejection_reason_tg;
    if old.status = 'pending' and new.status = 'active' then new.status := 'pending'; end if;
    if old.status = 'rejected' then new.status := old.status; end if;
  end if;

  if new.status = 'active' and old.status <> 'active' then
    new.published_at := now();
  else
    new.published_at := old.published_at;
  end if;
  return new;
end $$;

create or replace function private.listings_after() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.status = 'pending'
     and (tg_op = 'INSERT' or old.status <> 'pending' or new.updated_at <> old.updated_at)
     and new.moderation is null
     and private.setting('moderation', 'mode', 'ai') = 'ai' then
    perform private.call_function('moderate-listing', jsonb_build_object('listing_id', new.id));
  end if;
  return new;
end $$;
create trigger listings_after after insert or update on public.listings
for each row execute function private.listings_after();

alter policy "active listings are public" on public.listings
  using (status = 'active' or owner_id = (select auth.uid()) or (select private.is_staff()));

create policy "staff read hidden phones" on public.listing_private for select to authenticated
  using ((select private.is_staff()));
create policy "staff read phones" on public.profile_private for select to authenticated
  using ((select private.is_staff()));

-- Staff decision on a listing: approve | reject | archive.
create or replace function public.admin_moderate_listing(
  p_listing uuid, p_decision text, p_reason text default null, p_reason_tg text default null
) returns void language plpgsql security definer set search_path = '' as $$
declare
  me uuid := private.require_staff();
  l public.listings;
begin
  select * into l from public.listings where id = p_listing;
  if not found then raise exception 'listing_not_found' using errcode = 'P0002'; end if;
  if p_decision = 'approve' then
    update public.listings set status = 'active', published_at = now(), rejection_reason = null,
      rejection_reason_tg = null, moderated_at = now(), moderated_by = me
    where id = p_listing;
    perform private.notify(l.owner_id, 'listingApproved', 'Объявление опубликовано', l.title,
      jsonb_build_object('title', l.title, 'listingId', l.id));
  elsif p_decision = 'reject' then
    update public.listings set status = 'rejected', rejection_reason = coalesce(nullif(btrim(p_reason), ''), 'Нарушение правил'),
      rejection_reason_tg = nullif(btrim(p_reason_tg), ''), moderated_at = now(), moderated_by = me
    where id = p_listing;
    perform private.notify(l.owner_id, 'listingRejected', 'Объявление отклонено', coalesce(p_reason, ''),
      jsonb_build_object('title', l.title, 'listingId', l.id, 'reason', p_reason, 'reason_tg', p_reason_tg));
  elsif p_decision = 'archive' then
    update public.listings set status = 'archived', moderated_at = now(), moderated_by = me where id = p_listing;
  else
    raise exception 'bad_decision' using errcode = '22023';
  end if;
  perform private.audit('listing.' || p_decision, 'listing', p_listing::text,
    jsonb_build_object('title', l.title, 'reason', p_reason));
end $$;

create or replace function public.admin_delete_listing(p_listing uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare me uuid := private.require_staff(); l public.listings;
begin
  select * into l from public.listings where id = p_listing;
  if not found then return; end if;
  delete from public.listings where id = p_listing;
  perform private.audit('listing.delete', 'listing', p_listing::text, jsonb_build_object('title', l.title, 'owner', l.owner_id));
end $$;

-- Ask the AI to check a listing again (any status).
create or replace function public.admin_recheck_listing(p_listing uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  perform private.require_staff();
  perform private.call_function('moderate-listing', jsonb_build_object('listing_id', p_listing, 'force', true));
  perform private.audit('listing.ai_recheck', 'listing', p_listing::text);
end $$;

-- ── Users ───────────────────────────────────────────────────────────────
create or replace function public.admin_set_user_blocked(p_user uuid, p_blocked boolean, p_reason text default null)
returns void language plpgsql security definer set search_path = '' as $$
begin
  perform private.require_staff();
  if exists (select 1 from public.staff s where s.user_id = p_user) and not private.is_admin() then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  update public.profiles set is_blocked = p_blocked where id = p_user;
  if p_blocked then
    update public.listings set status = 'rejected',
      rejection_reason = coalesce(nullif(btrim(p_reason), ''), 'Аккаунт заблокирован'),
      moderated_at = now(), moderated_by = auth.uid()
    where owner_id = p_user and status in ('active', 'pending');
  end if;
  perform private.notify(p_user, 'system',
    case when p_blocked then 'Аккаунт заблокирован' else 'Аккаунт разблокирован' end,
    coalesce(p_reason, ''), jsonb_build_object('code', case when p_blocked then 'blocked' else 'unblocked' end));
  perform private.audit(case when p_blocked then 'user.block' else 'user.unblock' end, 'user', p_user::text,
    jsonb_build_object('reason', p_reason));
end $$;

create or replace function public.admin_set_staff(p_user uuid, p_role text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not private.is_admin() then raise exception 'forbidden' using errcode = '42501'; end if;
  if p_user = auth.uid() then raise exception 'own_role' using errcode = '22023'; end if;
  if p_role is null or p_role = '' then
    delete from public.staff where user_id = p_user;
  else
    insert into public.staff (user_id, role) values (p_user, p_role)
    on conflict (user_id) do update set role = excluded.role;
  end if;
  perform private.audit('staff.set', 'user', p_user::text, jsonb_build_object('role', p_role));
end $$;

create or replace function public.admin_search_users(p_query text default '', p_limit integer default 50)
returns jsonb language plpgsql stable security definer set search_path = '' as $$
declare q text := lower(btrim(coalesce(p_query, '')));
begin
  perform private.require_staff();
  return coalesce((
    select jsonb_agg(row_to_json(u) order by u.created_at desc)
    from (
      select p.id, p.name, p.region_id, p.account_type, p.is_phone_verified, p.is_blocked, p.created_at,
             pp.phone, s.role as staff_role,
             (select count(*) from public.listings l where l.owner_id = p.id) as listings,
             (select count(*) from public.listings l where l.owner_id = p.id and l.status = 'active') as active_listings,
             (select count(*) from public.reports r join public.listings l on l.id = r.listing_id where l.owner_id = p.id) as reports,
             (select count(*) from public.message_flags f where f.sender_id = p.id) as flags
      from public.profiles p
      left join public.profile_private pp on pp.id = p.id
      left join public.staff s on s.user_id = p.id
      where q = '' or lower(coalesce(p.name, '')) like '%' || q || '%' or coalesce(pp.phone, '') like '%' || q || '%'
        or p.id::text = q
      order by p.created_at desc
      limit least(greatest(coalesce(p_limit, 50), 1), 200)
    ) u
  ), '[]'::jsonb);
end $$;

-- ── Reports ─────────────────────────────────────────────────────────────
alter table public.reports
  add column status text not null default 'open' check (status in ('open', 'resolved', 'dismissed')),
  add column resolved_by uuid references public.profiles(id) on delete set null,
  add column resolution text;
create index reports_open_idx on public.reports (created_at) where status = 'open';
create index reports_resolved_by_idx on public.reports (resolved_by);
create policy "staff read reports" on public.reports for select to authenticated
  using ((select private.is_staff()));

create or replace function public.admin_resolve_report(p_report uuid, p_status text, p_resolution text default null)
returns void language plpgsql security definer set search_path = '' as $$
begin
  perform private.require_staff();
  if p_status not in ('resolved', 'dismissed') then raise exception 'bad_status' using errcode = '22023'; end if;
  update public.reports set status = p_status, resolution = p_resolution, resolved_by = auth.uid(), resolved_at = now()
  where id = p_report;
  perform private.audit('report.' || p_status, 'report', p_report::text, jsonb_build_object('resolution', p_resolution));
end $$;

-- ── Chat safety ─────────────────────────────────────────────────────────
alter table public.messages add column hidden boolean not null default false;

-- Messages from the platform inside a chat (safety warnings). Shown to
-- both participants, or only to [for_user].
create table public.chat_notices (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  for_user uuid references public.profiles(id) on delete cascade,
  code text not null,
  text_ru text not null,
  text_tg text not null,
  created_at timestamptz not null default now()
);
create index chat_notices_conversation_idx on public.chat_notices (conversation_id, created_at);
create index chat_notices_for_user_idx on public.chat_notices (for_user);
alter table public.chat_notices enable row level security;
create policy "participants read notices" on public.chat_notices for select to authenticated
  using ((select private.is_staff()) or (
    (for_user is null or for_user = (select auth.uid()))
    and exists (select 1 from public.conversations c
      where c.id = conversation_id and (select auth.uid()) in (c.buyer_id, c.seller_id))));

alter policy "participants read messages" on public.messages
  using (
    (select private.is_staff())
    or (exists (select 1 from public.conversations c
          where c.id = conversation_id and (select auth.uid()) in (c.buyer_id, c.seller_id))
        and (not hidden or sender_id = (select auth.uid())))
  );

alter policy "participants send messages" on public.messages
  with check (sender_id = (select auth.uid()) and not hidden
    and not exists (select 1 from public.profiles p where p.id = (select auth.uid()) and p.is_blocked)
    and exists (select 1 from public.conversations c
      where c.id = conversation_id
        and (select auth.uid()) in (c.buyer_id, c.seller_id)
        and not c.buyer_blocked and not c.seller_blocked));

create policy "staff read conversations" on public.conversations for select to authenticated
  using ((select private.is_staff()));

create table public.message_flags (
  id bigint generated always as identity primary key,
  message_id uuid not null references public.messages(id) on delete cascade,
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  sender_id uuid references public.profiles(id) on delete set null,
  risk text not null check (risk in ('warn', 'block')),
  category text not null,
  reason text not null default '',
  status text not null default 'open' check (status in ('open', 'reviewed')),
  reviewed_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now()
);
create index message_flags_open_idx on public.message_flags (created_at desc) where status = 'open';
create index message_flags_message_idx on public.message_flags (message_id);
create index message_flags_conversation_idx on public.message_flags (conversation_id);
create index message_flags_sender_idx on public.message_flags (sender_id);
create index message_flags_reviewed_by_idx on public.message_flags (reviewed_by);
alter table public.message_flags enable row level security;
create policy "staff read flags" on public.message_flags for select to authenticated
  using ((select private.is_staff()));

create or replace function public.admin_review_flag(p_flag bigint, p_unhide boolean default false)
returns void language plpgsql security definer set search_path = '' as $$
declare f public.message_flags;
begin
  perform private.require_staff();
  update public.message_flags set status = 'reviewed', reviewed_by = auth.uid() where id = p_flag returning * into f;
  if p_unhide and f.message_id is not null then
    update public.messages set hidden = false where id = f.message_id;
  end if;
  perform private.audit('flag.review', 'message_flag', p_flag::text, jsonb_build_object('unhide', p_unhide));
end $$;

-- New message: counters, a notification for the other person, AI check.
create or replace function private.on_message_sent() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  c public.conversations;
  recipient uuid;
  sender_name text;
begin
  update public.conversations x set
    last_message = left(new.text, 200),
    last_sender_id = new.sender_id,
    updated_at = new.created_at,
    buyer_unread = case when new.sender_id = x.seller_id then x.buyer_unread + 1 else x.buyer_unread end,
    seller_unread = case when new.sender_id = x.buyer_id then x.seller_unread + 1 else x.seller_unread end,
    buyer_hidden = false,
    seller_hidden = false
  where x.id = new.conversation_id
  returning * into c;
  recipient := case when new.sender_id = c.buyer_id then c.seller_id else c.buyer_id end;
  select coalesce(nullif(btrim(name), ''), 'DARYOB') into sender_name from public.profiles where id = new.sender_id;
  perform private.notify(recipient, 'newMessage', sender_name, left(new.text, 200),
    jsonb_build_object('title', c.listing_title, 'conversationId', c.id, 'messageId', new.id));
  if private.setting('moderation', 'chat_ai', 'true') = 'true' then
    perform private.call_function('moderate-message', jsonb_build_object('message_id', new.id));
  end if;
  return new;
end $$;

-- ── Support ─────────────────────────────────────────────────────────────
create table public.support_tickets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references public.profiles(id) on delete cascade,
  subject text not null check (char_length(subject) between 1 and 200),
  status text not null default 'open' check (status in ('open', 'answered', 'closed')),
  last_message text,
  user_unread integer not null default 0,
  staff_unread integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index support_tickets_user_idx on public.support_tickets (user_id, updated_at desc);
create index support_tickets_status_idx on public.support_tickets (status, updated_at desc);

create table public.support_messages (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid not null references public.support_tickets(id) on delete cascade,
  sender_id uuid default auth.uid() references public.profiles(id) on delete set null,
  is_staff boolean not null default false,
  text text not null check (char_length(text) between 1 and 4000),
  created_at timestamptz not null default now()
);
create index support_messages_ticket_idx on public.support_messages (ticket_id, created_at);
create index support_messages_sender_idx on public.support_messages (sender_id);

alter table public.support_tickets enable row level security;
alter table public.support_messages enable row level security;

create policy "own or staff tickets" on public.support_tickets for select to authenticated
  using (user_id = (select auth.uid()) or (select private.is_staff()));
create policy "open own ticket" on public.support_tickets for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy "own or staff ticket messages" on public.support_messages for select to authenticated
  using ((select private.is_staff()) or exists (
    select 1 from public.support_tickets t where t.id = ticket_id and t.user_id = (select auth.uid())));
create policy "write ticket messages" on public.support_messages for insert to authenticated
  with check (sender_id = (select auth.uid()) and (
    (select private.is_staff()) or exists (
      select 1 from public.support_tickets t where t.id = ticket_id and t.user_id = (select auth.uid()))));

create or replace function private.support_ticket_guard() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if private.is_privileged() then return new; end if;
  new.status := 'open';
  new.last_message := null;
  new.user_unread := 0;
  new.staff_unread := 0;
  new.created_at := now();
  new.updated_at := now();
  return new;
end $$;
create trigger support_ticket_guard before insert on public.support_tickets
for each row execute function private.support_ticket_guard();

create or replace function private.support_message_before() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if not private.is_privileged() then
    new.is_staff := private.is_staff() and not exists (
      select 1 from public.support_tickets t where t.id = new.ticket_id and t.user_id = auth.uid());
    new.created_at := now();
  end if;
  return new;
end $$;
create trigger support_message_before before insert on public.support_messages
for each row execute function private.support_message_before();

create or replace function private.support_message_after() returns trigger
language plpgsql security definer set search_path = '' as $$
declare t public.support_tickets;
begin
  update public.support_tickets set
    last_message = left(new.text, 200),
    updated_at = new.created_at,
    status = case when new.is_staff then 'answered' else 'open' end,
    user_unread = case when new.is_staff then user_unread + 1 else user_unread end,
    staff_unread = case when new.is_staff then staff_unread else staff_unread + 1 end
  where id = new.ticket_id
  returning * into t;
  if new.is_staff then
    perform private.notify(t.user_id, 'system', 'Ответ поддержки', left(new.text, 200),
      jsonb_build_object('ticketId', t.id, 'code', 'support_reply'));
  end if;
  return new;
end $$;
create trigger support_message_after after insert on public.support_messages
for each row execute function private.support_message_after();

create or replace function public.support_mark_read(p_ticket uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  update public.support_tickets set
    user_unread = case when user_id = auth.uid() then 0 else user_unread end,
    staff_unread = case when private.is_staff() and user_id <> auth.uid() then 0 else staff_unread end
  where id = p_ticket and (user_id = auth.uid() or private.is_staff());
end $$;

create or replace function public.admin_close_ticket(p_ticket uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  perform private.require_staff();
  update public.support_tickets set status = 'closed', staff_unread = 0 where id = p_ticket;
  perform private.audit('ticket.close', 'ticket', p_ticket::text);
end $$;

-- ── Settings and dashboard ──────────────────────────────────────────────
create or replace function public.admin_set_setting(p_key text, p_value jsonb) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not private.is_admin() then raise exception 'forbidden' using errcode = '42501'; end if;
  insert into public.app_settings (key, value, updated_at, updated_by)
  values (p_key, p_value, now(), auth.uid())
  on conflict (key) do update set value = excluded.value, updated_at = now(), updated_by = auth.uid();
  perform private.audit('setting.set', 'setting', p_key, p_value);
end $$;

create or replace function public.admin_stats() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  perform private.require_staff();
  return jsonb_build_object(
    'users', (select count(*) from public.profiles),
    'users_today', (select count(*) from public.profiles where created_at > now() - interval '1 day'),
    'users_blocked', (select count(*) from public.profiles where is_blocked),
    'listings_active', (select count(*) from public.listings where status = 'active'),
    'listings_pending', (select count(*) from public.listings where status = 'pending'),
    'listings_rejected', (select count(*) from public.listings where status = 'rejected'),
    'listings_today', (select count(*) from public.listings where created_at > now() - interval '1 day'),
    'reports_open', (select count(*) from public.reports where status = 'open'),
    'tickets_open', (select count(*) from public.support_tickets where status = 'open'),
    'flags_open', (select count(*) from public.message_flags where status = 'open'),
    'messages_today', (select count(*) from public.messages where created_at > now() - interval '1 day'),
    'ai_configured', (select value->>'ai_configured' from public.app_settings where key = 'ai_status')
  );
end $$;

-- ── Devices: notifications without push services ────────────────────────
-- The app registers a random token per install. A background task on the
-- phone asks for new notifications with it (no login session needed).
-- fcm_token is for Firebase push once a Firebase project is connected.
create table public.devices (
  id uuid primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  pull_token_hash text not null,
  fcm_token text,
  platform text,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);
create index devices_user_idx on public.devices (user_id);
alter table public.devices enable row level security;

create or replace function public.register_device(p_device uuid, p_token text, p_platform text default null, p_fcm text default null)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'not_signed_in' using errcode = '42501'; end if;
  if char_length(coalesce(p_token, '')) < 32 then raise exception 'bad_token' using errcode = '22023'; end if;
  insert into public.devices (id, user_id, pull_token_hash, platform, fcm_token)
  values (p_device, auth.uid(), encode(extensions.digest(p_token, 'sha256'), 'hex'), left(p_platform, 20), p_fcm)
  on conflict (id) do update set user_id = auth.uid(),
    pull_token_hash = excluded.pull_token_hash, platform = excluded.platform,
    fcm_token = coalesce(excluded.fcm_token, public.devices.fcm_token), last_seen_at = now();
end $$;
revoke execute on function public.register_device(uuid, text, text, text) from public, anon;
grant execute on function public.register_device(uuid, text, text, text) to authenticated;

create or replace function public.unregister_device(p_device uuid) returns void
language sql security definer set search_path = '' as $$
  update public.devices set pull_token_hash = 'signed-out', fcm_token = null
  where id = p_device and user_id = auth.uid();
$$;
revoke execute on function public.unregister_device(uuid) from public, anon;
grant execute on function public.unregister_device(uuid) to authenticated;

create or replace function public.pull_notifications(p_device uuid, p_token text, p_since timestamptz)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare d public.devices;
begin
  select * into d from public.devices
  where id = p_device and pull_token_hash = encode(extensions.digest(coalesce(p_token, ''), 'sha256'), 'hex');
  if not found then return null; end if;
  update public.devices set last_seen_at = now() where id = d.id;
  return coalesce((
    select jsonb_agg(jsonb_build_object('id', n.id, 'kind', n.kind, 'title', n.title, 'body', n.body,
                                        'data', n.data, 'created_at', n.created_at) order by n.created_at)
    from (select * from public.notifications
          where user_id = d.user_id and read_at is null
            and created_at > greatest(coalesce(p_since, now() - interval '1 day'), now() - interval '3 days')
          order by created_at limit 20) n
  ), '[]'::jsonb);
end $$;
grant execute on function public.pull_notifications(uuid, text, timestamptz) to anon, authenticated;

-- ── Places: cities, towns, villages (GeoNames, CC BY 4.0) ───────────────
create table public.places (
  id bigint primary key,
  kind text not null check (kind in ('city', 'town', 'village', 'quarter', 'district')),
  name_ru text not null,
  name_tg text not null,
  name_en text not null,
  region_id text not null,
  city_id text,
  district text,
  lat double precision not null,
  lng double precision not null,
  population integer not null default 0,
  search text not null
);
create index places_search_trgm_idx on public.places using gin (search extensions.gin_trgm_ops);
alter table public.places enable row level security;
create policy "places are public" on public.places for select to anon, authenticated using (true);

create or replace function public.search_places(p_query text, p_limit integer default 20)
returns setof public.places language sql stable set search_path = '' as $$
  select p.* from public.places p
  where char_length(btrim(coalesce(p_query, ''))) >= 2
    and p.search like '%' || lower(btrim(p_query)) || '%'
  order by
    (p.search like lower(btrim(p_query)) || '%') desc,
    case p.kind when 'city' then 0 when 'town' then 1 when 'district' then 2 when 'village' then 3 else 4 end,
    p.population desc, p.name_ru
  limit least(greatest(coalesce(p_limit, 20), 1), 50);
$$;

-- ── Realtime ────────────────────────────────────────────────────────────
alter publication supabase_realtime add table public.support_messages;
alter publication supabase_realtime add table public.support_tickets;
alter publication supabase_realtime add table public.notifications;
alter publication supabase_realtime add table public.chat_notices;

-- ── Test data from development: hide it ─────────────────────────────────
update public.listings set status = 'archived'
where description = 'Проверка сервера' or title like 'RT diag%' or title like 'iPhone 13 LIVE%';

-- Staff functions: signed-in users only (each checks the role itself).
do $$
declare f record;
begin
  for f in select p.oid::regprocedure as sig from pg_proc p join pg_namespace n on n.oid = p.pronamespace
           where n.nspname = 'public' and (p.proname like 'admin\_%' or p.proname = 'support_mark_read')
  loop
    execute format('revoke execute on function %s from public, anon', f.sig);
    execute format('grant execute on function %s to authenticated', f.sig);
  end loop;
end $$;
