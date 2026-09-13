-- 0024 проверка личности — дело исполнителя, а не заказчика.
--
-- Проверка существует ради одного: площадка платит живому человеку и должна
-- знать, кому. Заказчик денег не получает — он платит, — поэтому его паспорт
-- площадке не нужен, и спрашивать его означало бы собирать документы без
-- причины. Самые безопасные персональные данные — те, которых у вас нет.
--
-- Правило держится в трёх местах сразу: в интерфейсе, в сервисе и здесь.
-- Здесь — потому что скрипт, миграция данных или будущий модуль тоже могут
-- создать строку, а база не должна позволить ей появиться.

CREATE OR REPLACE FUNCTION identity_requires_freelancer() RETURNS trigger AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM user_roles r WHERE r.user_id = NEW.user_id AND r.role = 'developer'
  ) THEN
    RAISE EXCEPTION 'проверка личности заводится только исполнителям (user_id=%)', NEW.user_id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER identity_verifications_freelancer_only
  BEFORE INSERT OR UPDATE OF user_id ON identity_verifications
  FOR EACH ROW EXECUTE FUNCTION identity_requires_freelancer();

-- Дела, заведённые до этого правила на аккаунты без роли исполнителя, вместе
-- со снимками. Строки документов удаляются, а файлы подберёт тот же рабочий
-- процесс, что чистит их по сроку хранения: он ищет записи, у которых срок
-- прошёл, поэтому сначала ставим им срок «сейчас», а потом уже удаляем дело.
UPDATE identity_documents d
SET retention_expires_at = now() - interval '1 day'
WHERE d.deleted_at IS NULL
  AND EXISTS (
    SELECT 1 FROM identity_verifications v
    WHERE v.id = d.verification_id
      AND NOT EXISTS (
        SELECT 1 FROM user_roles r WHERE r.user_id = v.user_id AND r.role = 'developer'
      )
  );

-- Требование проходить проверку до оплачиваемой работы. Включено по
-- умолчанию: площадка, которая переводит деньги незнакомцам, должна знать их
-- имена. Выключается, если оператору это не нужно.
INSERT INTO platform_settings (key, value, description, scope)
VALUES ('identity.required_for_work', 'true'::jsonb,
        'Требовать подтверждённую личность исполнителя до отклика, публикации услуги и найма.',
        'private')
ON CONFLICT (key) DO NOTHING;
