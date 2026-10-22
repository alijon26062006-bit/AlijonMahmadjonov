-- служебная функция политик доступа не должна быть доступна через /rest/v1/rpc
create schema if not exists private;
revoke all on schema private from public, anon;
grant usage on schema private to authenticated;
alter function public.owns_shop(uuid) set schema private;
