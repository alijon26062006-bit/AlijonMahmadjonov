'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import styles from '../admin.module.css';
import users_styles from './users.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Avatar } from '@/components/ui/Avatar';
import { Input, Select } from '@/components/ui/Field';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconSearch, IconUser, IconChevronRight } from '@/components/ui/Icon';
import { list } from '@/lib/api';
import { shortDate, timeAgo } from '@/lib/format';
import { countryName, roleLabel } from '@/lib/labels';
import { identityTone, identityStatusLabel, accountStatusLabel, accountTone } from '@/lib/admin';
import type { AdminUser } from '@/lib/types';

// The quick filters, in the order support actually uses them. Each one is a
// pair of query values rather than a magic string, so the list and the URL
// never disagree about what "На проверке" means.
const QUICK = [
  { key: 'all', label: 'Все', params: {} },
  { key: 'clients', label: 'Заказчики', params: { role: 'client' } },
  { key: 'freelancers', label: 'Исполнители', params: { role: 'developer' } },
  { key: 'staff', label: 'Сотрудники', params: { role: 'admin' } },
  { key: 'verified', label: 'Личность подтверждена', params: { identity: 'approved' } },
  { key: 'unverified', label: 'Без проверки', params: { identity: 'none' } },
  { key: 'review', label: 'На проверке', params: { identity: 'under_review' } },
  { key: 'rejected', label: 'Отказано', params: { identity: 'rejected' } },
  { key: 'suspended', label: 'Приостановлены', params: { status: 'suspended' } },
  { key: 'banned', label: 'Заблокированы', params: { status: 'banned' } },
  { key: 'reported', label: 'С жалобами', params: { reported: 'true' } },
] as const;

const PAGE = 30;

export default function AdminUsersPage() {
  const [text, setText] = useState('');
  const [quick, setQuick] = useState<string>('all');
  const [advanced, setAdvanced] = useState(false);
  const [country, setCountry] = useState('');
  const [listed, setListed] = useState(false);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [rows, setRows] = useState<AdminUser[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [denied, setDenied] = useState(false);

  const params = useMemo(() => {
    const quickParams = QUICK.find((item) => item.key === quick)?.params ?? {};
    const query = new URLSearchParams({ limit: String(PAGE), ...quickParams });
    if (text.trim()) query.set('q', text.trim());
    if (country.trim()) query.set('country', country.trim().toUpperCase());
    if (listed) query.set('listed', 'true');
    if (from) query.set('registered_from', from);
    if (to) query.set('registered_to', to);
    return query;
  }, [quick, text, country, listed, from, to]);

  const load = useCallback(
    async (nextOffset: number) => {
      setRows(null);
      setDenied(false);
      const query = new URLSearchParams(params);
      query.set('offset', String(nextOffset));
      try {
        const response = await list<AdminUser[]>(`/admin/users?${query.toString()}`);
        setRows(response.data ?? []);
        setTotal(Number(response.meta?.total ?? 0));
        setOffset(nextOffset);
      } catch (failure) {
        setRows([]);
        setDenied((failure as { status?: number })?.status === 403);
      }
    },
    [params],
  );

  useEffect(() => {
    void load(0);
    // Text is applied on submit; everything else filters as it is chosen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quick, country, listed, from, to]);

  return (
    <>
      <TopBar back="/admin" title="Пользователи" />
      <div className={`av-page av-stack ${styles.shell}`}>
        <Card>
          <form
            className={users_styles.search}
            onSubmit={(event) => {
              event.preventDefault();
              void load(0);
            }}
          >
            <Input
              label="Поиск"
              placeholder="Имя, @логин, почта, телефон или AVX-код"
              hint="Номер документа здесь не ищется и в списке не показывается."
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
            <Button type="submit" icon={<IconSearch size={16} />}>
              Найти
            </Button>
          </form>

          <div className={users_styles.chips} role="group" aria-label="Быстрые фильтры">
            {QUICK.map((item) => (
              <button
                key={item.key}
                type="button"
                className={[users_styles.chip, quick === item.key ? users_styles.chipOn : ''].join(' ')}
                aria-pressed={quick === item.key}
                onClick={() => setQuick(item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>

          <button type="button" className={users_styles.more} onClick={() => setAdvanced((open) => !open)}>
            {advanced ? 'Свернуть условия' : 'Больше условий'}
          </button>

          {advanced ? (
            <div className={users_styles.advanced}>
              <Input
                label="Страна"
                placeholder="RU, UZ, KZ…"
                value={country}
                onChange={(event) => setCountry(event.target.value)}
              />
              <Input
                label="Зарегистрирован с"
                type="date"
                value={from}
                onChange={(event) => setFrom(event.target.value)}
              />
              <Input label="по" type="date" value={to} onChange={(event) => setTo(event.target.value)} />
              <Select
                label="В каталоге исполнителей"
                value={listed ? 'yes' : ''}
                onChange={(event) => setListed(event.target.value === 'yes')}
              >
                <option value="">Неважно</option>
                <option value="yes">Только опубликованные</option>
              </Select>
            </div>
          ) : null}
        </Card>

        {rows === null ? (
          <SkeletonList count={5} />
        ) : denied ? (
          <EmptyState
            icon={<IconUser size={20} />}
            title="Нет доступа к списку пользователей"
            description="Нужно право users.view. Его выдаёт администратор поимённо."
          />
        ) : rows.length === 0 ? (
          <EmptyState icon={<IconUser size={20} />} title="Никого не нашли" description="Измените условия поиска." />
        ) : (
          <>
            <p className="av-small av-muted">
              Найдено: {total}
              {total > PAGE ? ` · показаны ${offset + 1}–${Math.min(offset + PAGE, total)}` : ''}
            </p>
            <div className={users_styles.grid}>
              {rows.map((user) => (
                <Link key={user.id} href={`/admin/users/${user.id}`} className={users_styles.card}>
                  <Avatar src={user.photo_url} name={user.full_name} size={48} verified={user.identity_verified} />
                  <div className="av-grow">
                    <p className="av-strong">
                      {user.full_name} <span className="av-faint">@{user.username}</span>
                    </p>
                    <p className="av-xs av-faint">
                      {user.email}
                      {user.country_code ? ` · ${countryName(user.country_code)}` : ''}
                      {user.city ? `, ${user.city}` : ''}
                    </p>
                    <p className="av-xs av-faint">
                      {user.reference} · с {shortDate(user.created_at)}
                      {user.last_seen_at ? ` · заходил ${timeAgo(user.last_seen_at)}` : ''}
                    </p>
                    <div className={users_styles.badges}>
                      {user.roles.map((role) => (
                        <Badge key={role} tone="brand" size="sm">
                          {roleLabel(role)}
                        </Badge>
                      ))}
                      {user.status !== 'active' ? (
                        <Badge tone={accountTone(user.status)} size="sm">
                          {accountStatusLabel(user.status)}
                        </Badge>
                      ) : null}
                      <Badge tone={identityTone(user.identity_status)} size="sm">
                        {identityStatusLabel(user.identity_status)}
                      </Badge>
                      {!user.email_verified ? (
                        <Badge tone="warning" size="sm">
                          Почта не подтверждена
                        </Badge>
                      ) : null}
                    </div>
                  </div>
                  <IconChevronRight size={18} />
                </Link>
              ))}
            </div>

            {total > PAGE ? (
              <div className="av-row" style={{ justifyContent: 'space-between' }}>
                <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => void load(Math.max(0, offset - PAGE))}>
                  Назад
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={offset + PAGE >= total}
                  onClick={() => void load(offset + PAGE)}
                >
                  Дальше
                </Button>
              </div>
            ) : null}
          </>
        )}
      </div>
    </>
  );
}
