-- Разворот в русскоязычный маркетплейс оставил два столбца с прежними
-- значениями по умолчанию: валюта ставки и занятость.
--
-- Валюта по умолчанию была USD — для площадки, где цены в рублях, это
-- означало, что исполнитель, не тронувший поле, выставлял ставку в чужой
-- валюте и сам того не видел.
--
-- Занятость по умолчанию была 'unavailable'. Человек, который только что
-- зарегистрировался, чтобы искать работу, попадал в каталог с подписью
-- «Недоступен» — ровно обратное тому, зачем он пришёл. Значение по
-- умолчанию теперь 'available'; кто занят, скажет об этом сам.
--
-- Меняются только значения по умолчанию для новых строк. Уже заполненные
-- анкеты не переписываются: это данные людей, а не наша опечатка.

ALTER TABLE developer_profiles
  ALTER COLUMN rate_currency SET DEFAULT 'RUB',
  ALTER COLUMN availability  SET DEFAULT 'available';

-- Незавершённые анкеты — исключение: их владельцы ещё ни разу не видели
-- эти поля, поэтому там стоит не выбор человека, а прежнее умолчание.
UPDATE developer_profiles
   SET rate_currency = 'RUB'
 WHERE onboarding_completed_at IS NULL
   AND rate_currency = 'USD'
   AND hourly_rate_minor IS NULL
   AND min_project_minor IS NULL;

UPDATE developer_profiles
   SET availability = 'available'
 WHERE onboarding_completed_at IS NULL
   AND availability = 'unavailable';

-- То же и для заказов: проект, созданный без явной валюты, теперь рублёвый.
ALTER TABLE projects ALTER COLUMN currency SET DEFAULT 'RUB';
