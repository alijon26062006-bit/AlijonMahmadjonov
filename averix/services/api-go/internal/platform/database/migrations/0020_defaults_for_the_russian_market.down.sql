ALTER TABLE projects ALTER COLUMN currency SET DEFAULT 'USD';

ALTER TABLE developer_profiles
  ALTER COLUMN rate_currency SET DEFAULT 'USD',
  ALTER COLUMN availability  SET DEFAULT 'unavailable';
