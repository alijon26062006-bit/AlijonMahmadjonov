-- ============================================================
-- AVERIX — показатели на главной и недостающие статусы заявок
--
-- Цифры больше не зашиты в разметку: у каждой есть значение,
-- единица, подпись на двух языках и переключатель показа.
-- Показатель, который нельзя подтвердить, выключается в админке.
--
-- Существующие значения stat_years / stat_active / stat_accepted
-- сохраняются: к ним только добавляются соседние ключи.
-- ============================================================

INSERT INTO site_settings (key, value_ru, value_tj) VALUES
  ('stat_years_on',       '1', '1'),
  ('stat_years_unit',     '',  ''),
  ('stat_years_label',    'года в разработке', 'сол дар барномасозӣ'),

  ('stat_active_on',      '1', '1'),
  ('stat_active_unit',    '',  ''),
  ('stat_active_label',   'проекта в работе прямо сейчас', 'лоиҳа айни замон дар кор'),

  ('stat_accepted_on',    '1', '1'),
  ('stat_accepted_unit',  '%', '%'),
  ('stat_accepted_label', 'работ принято заказчиком', 'кор аз ҷониби фармоишгар қабул шуд');

-- ------------------------------------------------------------
-- Заявкам клиентов не хватало двух состояний: «отправили расчёт»
-- и «спам». В SQLite нельзя изменить CHECK у существующей колонки,
-- поэтому таблица пересобирается — со всеми строками, без потерь.
-- ------------------------------------------------------------
CREATE TABLE client_requests_new (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    telegram     TEXT,
    email        TEXT,
    project_type TEXT,
    budget       TEXT,
    message      TEXT,
    status       TEXT NOT NULL DEFAULT 'new'
                 CHECK (status IN ('new', 'contacted', 'estimate_sent',
                                   'in_progress', 'won', 'closed', 'spam')),
    admin_note   TEXT,
    ip           TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO client_requests_new
      (id, name, telegram, email, project_type, budget, message,
       status, admin_note, ip, created_at, updated_at)
SELECT id, name, telegram, email, project_type, budget, message,
       status, admin_note, ip, created_at, updated_at
  FROM client_requests;

DROP TABLE client_requests;
ALTER TABLE client_requests_new RENAME TO client_requests;
CREATE INDEX idx_requests_status ON client_requests(status, created_at DESC);
