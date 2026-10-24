-- ТЕСТ: зона открыта — заказы принимаются в любом городе и стране.
-- Перед запуском для людей: create or replace function private.zone_open() ... select false
-- (и open: false в client/js/config.js и seller/js/config.js) — снова только Шахритусский район.
create or replace function private.zone_open() returns boolean
language sql stable set search_path = ''
as $$ select true $$;

create or replace function private.delivery_quote(s_lat double precision, s_lng double precision, a_lat double precision, a_lng double precision)
returns table (km numeric, fee numeric, ok boolean) language plpgsql stable set search_path = ''
as $$
declare
  c_lat constant double precision := 37.267; c_lng constant double precision := 68.133;
  v_open boolean := private.zone_open();
  f_lat double precision; f_lng double precision; t_lat double precision; t_lng double precision;
  d numeric;
begin
  -- у кого нет метки на карте: в открытой зоне считаем его рядом с другим, иначе — в центре посёлка
  f_lat := coalesce(s_lat, case when v_open then a_lat end, c_lat); f_lng := coalesce(s_lng, case when v_open then a_lng end, c_lng);
  t_lat := coalesce(a_lat, case when v_open then s_lat end, c_lat); t_lng := coalesce(a_lng, case when v_open then s_lng end, c_lng);
  d := greatest(0.3, round((private.km_between(f_lat, f_lng, t_lat, t_lng) * 1.3)::numeric, 1));
  km := d;
  fee := case when d <= 2 then 15 when d <= 5 then 20 else 20 + ceil(d - 5) * 2 end;
  ok := d <= 30 and (v_open or a_lat is null or private.km_between(c_lat, c_lng, a_lat, a_lng) <= 15);
  return next;
end;
$$;
