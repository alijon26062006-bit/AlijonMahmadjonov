'use client';

import SettingsPage from '../page';

/**
 * Отдельный адрес для возврата из GitHub и для ссылок из уведомлений.
 * Это те же настройки, сразу открытые на вкладке интеграций.
 */
export default function GitHubSettingsPage() {
  return <SettingsPage initialTab="integrations" />;
}
