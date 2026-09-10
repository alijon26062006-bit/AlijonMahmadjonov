-- Провижининг может провалиться (nginx -t не прошёл, SSL не выпустился), и тогда
-- сайт не «pending» и не «active». Без отдельного состояния такой сайт вечно
-- показывался как «создаётся», хотя ждать было нечего.
ALTER TABLE sites
    MODIFY COLUMN status ENUM('pending','active','suspended','deleted','error')
    NOT NULL DEFAULT 'pending';
