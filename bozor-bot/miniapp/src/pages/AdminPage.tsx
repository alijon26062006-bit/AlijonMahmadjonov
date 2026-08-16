/** Админ-панель: очередь модерации, жалобы, пользователи, справочники, журнал. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, fmtPrice, photoUrl } from '../api/client';
import { Icon } from '../components/icons';
import { Empty, useAuth, useTgBackButton } from '../components/ui';

type Tab = 'queue' | 'reports' | 'users' | 'dicts' | 'log';

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'queue', label: 'Очередь', icon: 'archive' },
  { id: 'reports', label: 'Жалобы', icon: 'flag' },
  { id: 'users', label: 'Люди', icon: 'user' },
  { id: 'dicts', label: 'Справочники', icon: 'list' },
  { id: 'log', label: 'Журнал', icon: 'check' },
];

const REJECT_REASONS = [
  'Плохие фото', 'Недостоверная цена', 'Мало информации',
  'Реклама / спам', 'Не по теме площадки',
];

export default function AdminPage() {
  useTgBackButton(true);
  const user = useAuth();
  const [tab, setTab] = useState<Tab>('queue');

  const { data: stats } = useQuery<any>({
    queryKey: ['admin-stats'],
    queryFn: () => api('/api/admin/stats'),
    enabled: Boolean(user?.is_admin),
    refetchInterval: 30_000,
  });

  if (!user) return <Empty icon="lock" title="Нужен вход" />;
  if (!user.is_admin) {
    return <Empty icon="lock" title="Доступ только для администраторов"
                  note="Если вы админ — убедитесь, что ваш ID указан в настройках" />;
  }

  return (
    <div className="section fade-in">
      <h1 className="section-title">Администрирование</h1>

      {stats && (
        <div className="stat-row">
          <Stat label="На модерации" value={stats.pending} tone="amber" />
          <Stat label="Опубликовано" value={stats.approved} tone="green" />
          <Stat label="Жалобы" value={stats.reports_new} tone={stats.reports_new ? 'red' : 'gray'} />
          <Stat label="За сутки" value={stats.today} tone="gray" />
          <Stat label="Людей" value={stats.users} tone="gray" />
          {/* сколько моделей телефонов площадка уже узнаёт по IMEI */}
          <Stat label="Моделей по IMEI" value={stats.tac?.total} tone="gray" />
        </div>
      )}

      <div className="chips" style={{ margin: '16px 0' }}>
        {TABS.map((t) => (
          <button key={t.id} className={`chip ${tab === t.id ? 'on' : ''}`}
                  onClick={() => setTab(t.id)}>
            <Icon name={t.icon} size={14} /> {t.label}
            {t.id === 'queue' && stats?.pending > 0 && ` · ${stats.pending}`}
            {t.id === 'reports' && stats?.reports_new > 0 && ` · ${stats.reports_new}`}
          </button>
        ))}
      </div>

      {tab === 'queue' && <Queue />}
      {tab === 'reports' && <Reports />}
      {tab === 'users' && <Users />}
      {tab === 'dicts' && <Dicts />}
      {tab === 'log' && <Log />}

      {tab === 'queue' && stats?.by_category?.length > 0 && (
        <div className="section">
          <h3 className="field-label">Опубликовано по категориям</h3>
          <div className="specs">
            {stats.by_category.map((c: any) => (
              <div key={c.slug} className="spec-row">
                <span className="k">{c.title}</span>
                <span className="v">{c.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className={`stat stat-${tone}`}>
      <div className="stat-value">{value ?? 0}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

/* ─────────────────────────── Очередь ─────────────────────────── */

function Queue() {
  const qc = useQueryClient();
  const [rejecting, setRejecting] = useState<number | null>(null);
  const [customReason, setCustomReason] = useState('');

  const { data, isLoading } = useQuery<any>({
    queryKey: ['admin-queue'],
    queryFn: () => api('/api/admin/listings?status=pending'),
    refetchInterval: 20_000,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['admin-queue'] });
    qc.invalidateQueries({ queryKey: ['admin-stats'] });
  };

  const approve = useMutation({
    mutationFn: (id: number) => api(`/api/admin/listings/${id}/approve`, { method: 'POST' }),
    onSuccess: refresh,
    onError: refresh,     // 409 «уже обработано» — просто обновляем список
  });

  const reject = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      api(`/api/admin/listings/${id}/reject`, {
        method: 'POST', body: JSON.stringify({ reason }),
      }),
    onSuccess: () => { setRejecting(null); setCustomReason(''); refresh(); },
    onError: refresh,
  });

  if (isLoading) return <div className="skeleton" style={{ height: 140 }} />;
  const items = data?.items ?? [];
  if (!items.length) {
    return <Empty icon="check" title="Очередь пуста"
                  note="Новые объявления появятся здесь автоматически" />;
  }

  return (
    <>
      {items.map((l: any) => (
        <div key={l.id} className="mod-card fade-in">
          <div className="mod-photos">
            {l.photos.length
              ? l.photos.map((p: any, i: number) => (
                  <img key={i} src={photoUrl(p.thumb)} alt=""
                       onClick={() => window.open(photoUrl(p.full), '_blank')} />
                ))
              : <div className="mod-nophoto"><Icon name="image" size={22} /></div>}
          </div>

          <div className="mod-body">
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <b>{l.title}</b>
              <span className="badge badge-gray">{l.category}</span>
            </div>
            <div className="listing-price" style={{ fontSize: 'var(--fs-lg)', margin: '4px 0' }}>
              {fmtPrice(l.price, l.currency)}
            </div>
            <div className="subtitle">
              {[l.city, l.district, l.address].filter(Boolean).join(', ')}
            </div>
            {l.description && <p className="mod-desc">{l.description}</p>}

            {l.flag_note && (
              <div className="mod-flag"><Icon name="flag" size={14} /> {l.flag_note}</div>
            )}

            <div className="subtitle" style={{ marginTop: 6 }}>
              Автор: {l.author.username ? `@${l.author.username}` : l.author.name}
              {l.author.is_banned && <span className="badge badge-red" style={{ marginLeft: 6 }}>забанен</span>}
            </div>

            {rejecting === l.id ? (
              <div className="mod-reject">
                <div className="chips" style={{ marginBottom: 8 }}>
                  {REJECT_REASONS.map((r) => (
                    <button key={r} className="chip"
                            onClick={() => reject.mutate({ id: l.id, reason: r })}>
                      {r}
                    </button>
                  ))}
                </div>
                <div className="range-row">
                  <input placeholder="Своя причина"
                         value={customReason}
                         onChange={(e) => setCustomReason(e.target.value)} />
                  <button className="btn btn-danger"
                          disabled={!customReason.trim()}
                          onClick={() => reject.mutate({ id: l.id, reason: customReason })}>
                    Отклонить
                  </button>
                </div>
                <button className="btn btn-ghost btn-block" style={{ marginTop: 6 }}
                        onClick={() => setRejecting(null)}>Отмена</button>
              </div>
            ) : (
              <div className="my-actions">
                <button className="btn btn-primary" disabled={approve.isPending}
                        onClick={() => approve.mutate(l.id)}>
                  <Icon name="check" size={15} /> Одобрить
                </button>
                <button className="btn btn-danger" onClick={() => setRejecting(l.id)}>
                  <Icon name="x" size={15} /> Отклонить
                </button>
              </div>
            )}
          </div>
        </div>
      ))}
      {data.total > items.length && (
        <p className="subtitle" style={{ textAlign: 'center' }}>
          Показано {items.length} из {data.total}
        </p>
      )}
    </>
  );
}

/* ─────────────────────────── Жалобы ─────────────────────────── */

const REASON_LABEL: Record<string, string> = {
  spam: 'Спам', fake: 'Обман', already_sold: 'Уже продано',
  wrong_price: 'Неверная цена', offensive: 'Оскорбления',
  duplicate: 'Дубликат', other: 'Другое',
};

function Reports() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<any>({
    queryKey: ['admin-reports'],
    queryFn: () => api('/api/admin/reports?status=new'),
  });
  const resolve = useMutation({
    mutationFn: ({ id, accept }: { id: number; accept: boolean }) =>
      api(`/api/admin/reports/${id}/resolve?accept=${accept}`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-reports'] });
      qc.invalidateQueries({ queryKey: ['admin-stats'] });
    },
  });

  if (isLoading) return <div className="skeleton" style={{ height: 90 }} />;
  const items = data?.items ?? [];
  if (!items.length) return <Empty icon="check" title="Жалоб нет" />;

  return (
    <>
      {items.map((r: any) => (
        <div key={r.id} className="my-item fade-in" style={{ flexDirection: 'column' }}>
          <div>
            <span className="badge badge-red">{REASON_LABEL[r.reason] ?? r.reason}</span>
            <b style={{ marginLeft: 8 }}>{r.listing_title}</b>
          </div>
          {r.comment && <p className="subtitle">{r.comment}</p>}
          <div className="my-actions">
            <a className="btn" href={`/listing/${r.listing_public_id}`} target="_blank" rel="noreferrer">
              Открыть
            </a>
            <button className="btn btn-danger"
                    onClick={() => resolve.mutate({ id: r.id, accept: true })}>
              Снять объявление
            </button>
            <button className="btn"
                    onClick={() => resolve.mutate({ id: r.id, accept: false })}>
              Отклонить жалобу
            </button>
          </div>
        </div>
      ))}
    </>
  );
}

/* ─────────────────────────── Пользователи ─────────────────────────── */

function Users() {
  const qc = useQueryClient();
  const [q, setQ] = useState('');
  const { data, isLoading } = useQuery<any>({
    queryKey: ['admin-users', q],
    queryFn: () => api(`/api/admin/users?q=${encodeURIComponent(q)}`),
  });
  const ban = useMutation({
    mutationFn: ({ id, banned }: { id: number; banned: boolean }) =>
      api(`/api/admin/users/${id}/ban?banned=${banned}`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  return (
    <>
      <div className="searchbar" style={{ marginBottom: 12 }}>
        <input placeholder="Поиск по имени, @нику или ID"
               onKeyDown={(e) => {
                 if (e.key === 'Enter') setQ((e.target as HTMLInputElement).value);
               }} />
      </div>
      {isLoading && <div className="skeleton" style={{ height: 80 }} />}
      {(data?.items ?? []).map((u: any) => (
        <div key={u.id} className="my-item fade-in">
          <div style={{ flex: 1, minWidth: 0 }}>
            <b>{u.name}</b>
            {u.username && <span className="subtitle"> @{u.username}</span>}
            {u.is_admin && <span className="badge badge-green" style={{ marginLeft: 6 }}>админ</span>}
            {u.is_banned && <span className="badge badge-red" style={{ marginLeft: 6 }}>бан</span>}
            <div className="subtitle">
              ID {u.tg_id} · объявлений: {u.listings}
              {u.phone && ` · ${u.phone}`}
            </div>
            {!u.is_admin && (
              <div className="my-actions">
                <button className={u.is_banned ? 'btn' : 'btn btn-danger'}
                        onClick={() => ban.mutate({ id: u.id, banned: !u.is_banned })}>
                  {u.is_banned ? 'Разбанить' : 'Забанить'}
                </button>
              </div>
            )}
          </div>
        </div>
      ))}
    </>
  );
}

/* ─────────────────────────── Справочники ─────────────────────────── */

const AREAS = [
  ['cars', 'Автомобили'], ['phones', 'Телефоны'], ['computers', 'Компьютеры'],
  ['components', 'Комплектующие'], ['appliances', 'Бытовая техника'],
  ['tv_audio', 'ТВ и аудио'], ['tools', 'Инструмент'],
  ['moto_bike', 'Мото и вело'], ['electronics', 'Электроника'],
];

function Dicts() {
  const qc = useQueryClient();
  const [msg, setMsg] = useState('');
  const [city, setCity] = useState('');
  const [brand, setBrand] = useState('');
  const [brandArea, setBrandArea] = useState('cars');
  const [modelBrand, setModelBrand] = useState('');
  const [modelName, setModelName] = useState('');

  const { data: cities } = useQuery<any>({
    queryKey: ['dict-cities'], queryFn: () => api('/api/dicts/cities'),
  });

  const send = async (path: string, body: unknown, ok: string) => {
    try {
      await api(path, { method: 'POST', body: JSON.stringify(body) });
      setMsg(ok);
      qc.invalidateQueries({ queryKey: ['dict-cities'] });
    } catch (e) {
      const err = e as { status?: number };
      setMsg(err.status === 409 ? 'Уже есть в справочнике' : 'Не удалось добавить');
    }
  };

  return (
    <div className="fade-in">
      <p className="subtitle" style={{ marginBottom: 14 }}>
        Новые значения появляются в боте и на сайте сразу — перезапуск не нужен.
      </p>
      {msg && <div className="badge badge-green" style={{ marginBottom: 12 }}>{msg}</div>}

      <div className="field">
        <span className="field-label">Добавить город</span>
        <div className="range-row">
          <input placeholder="Название" value={city}
                 onChange={(e) => setCity(e.target.value)} />
          <button className="btn btn-primary" disabled={!city.trim()}
                  onClick={() => { send('/api/admin/dicts/cities', { name: city }, 'Город добавлен'); setCity(''); }}>
            Добавить
          </button>
        </div>
        <div className="field-hint">
          Сейчас в справочнике: {(cities?.items ?? []).length} городов
        </div>
      </div>

      <div className="field">
        <span className="field-label">Добавить бренд</span>
        <div className="range-row">
          <input placeholder="Название бренда" value={brand}
                 onChange={(e) => setBrand(e.target.value)} />
          <select style={{ width: 150, flex: 'none' }} value={brandArea}
                  onChange={(e) => setBrandArea(e.target.value)}>
            {AREAS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <button className="btn btn-primary btn-block" style={{ marginTop: 8 }}
                disabled={!brand.trim()}
                onClick={() => { send('/api/admin/dicts/brands', { name: brand, areas: [brandArea] }, 'Бренд добавлен'); setBrand(''); }}>
          Добавить бренд
        </button>
        <div className="field-hint">
          Если бренд уже есть — к нему добавится выбранная область применения.
        </div>
      </div>

      <div className="field">
        <span className="field-label">Добавить модель автомобиля</span>
        <div className="range-row">
          <input placeholder="Марка (точно как в списке)" value={modelBrand}
                 onChange={(e) => setModelBrand(e.target.value)} />
          <input placeholder="Модель" value={modelName}
                 onChange={(e) => setModelName(e.target.value)} />
        </div>
        <button className="btn btn-primary btn-block" style={{ marginTop: 8 }}
                disabled={!modelBrand.trim() || !modelName.trim()}
                onClick={() => { send('/api/admin/dicts/models', { brand: modelBrand, name: modelName, area: 'cars' }, 'Модель добавлена'); setModelName(''); }}>
          Добавить модель
        </button>
      </div>
    </div>
  );
}

/* ─────────────────────────── Журнал ─────────────────────────── */

const ACTION_LABEL: Record<string, string> = {
  approve: 'одобрил', reject: 'отклонил', archive: 'снял',
  ban_user: 'забанил', unban_user: 'разбанил', ban_author: 'забанил автора',
};

function Log() {
  const { data, isLoading } = useQuery<any>({
    queryKey: ['admin-log'], queryFn: () => api('/api/admin/log'),
  });
  if (isLoading) return <div className="skeleton" style={{ height: 90 }} />;
  const items = data?.items ?? [];
  if (!items.length) return <Empty icon="check" title="Журнал пуст" />;
  return (
    <div className="specs">
      {items.map((m: any) => (
        <div key={m.id} className="spec-row">
          <span className="k">
            {m.admin} {ACTION_LABEL[m.action] ?? m.action}
            {m.listing_id ? ` #${m.listing_id}` : ''}
            {m.reason ? ` — ${m.reason}` : ''}
          </span>
          <span className="v">
            {m.created_at ? new Date(m.created_at).toLocaleString('ru-RU',
              { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : ''}
          </span>
        </div>
      ))}
    </div>
  );
}
