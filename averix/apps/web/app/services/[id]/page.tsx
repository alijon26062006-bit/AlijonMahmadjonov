'use client';

import { use, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import styles from './service.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { BottomNav } from '@/components/nav/BottomNav';
import { Card } from '@/components/ui/Card';
import { Avatar } from '@/components/ui/Avatar';
import { Badge, Tag } from '@/components/ui/Badge';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import { Select, Textarea } from '@/components/ui/Field';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ReportSheet } from '@/components/domain/ReportSheet';
import { IconAlert, IconCheck, IconClock, IconRefresh, IconStarFilled } from '@/components/ui/Icon';
import { ApiFailure, get, post } from '@/lib/api';
import { days, money, plural } from '@/lib/format';
import { SERVICE_STATUS } from '@/lib/labels';
import { useSession } from '@/lib/session';
import type { Service } from '@/lib/types';

export default function ServicePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { session } = useSession();
  const [service, setService] = useState<Service | null>(null);
  const [failed, setFailed] = useState(false);
  const [tier, setTier] = useState(0);
  const [ordering, setOrdering] = useState(false);
  const [reporting, setReporting] = useState(false);

  const load = useCallback(async () => {
    setFailed(false);
    try {
      setService(await get<Service>(`/services/${id}`));
    } catch {
      setFailed(true);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (failed) {
    return (
      <>
        <TopBar back="/services" title="Услуга" />
        <main id="main" className="av-page">
          <EmptyState
            tone="error"
            icon={<IconAlert size={20} />}
            title="Услуга недоступна"
            description="Возможно, исполнитель снял её с публикации или она была скрыта модератором."
            action={<ButtonLink href="/services">В каталог услуг</ButtonLink>}
          />
        </main>
      </>
    );
  }

  if (!service) {
    return (
      <>
        <TopBar back="/services" title="Услуга" />
        <main id="main" className="av-page av-stack">
          <Skeleton height={200} radius="var(--av-radius-xl)" />
          <Skeleton height={28} width="70%" />
          <Skeleton height={140} />
        </main>
      </>
    );
  }

  const selected = service.tiers[tier] ?? service.tiers[0];
  const isClient = session?.active_role === 'client';

  return (
    <>
      <TopBar back="/services" title={service.is_owner ? 'Моя услуга' : 'Услуга'} />
      <main id="main" className={`av-page av-stack ${styles.shell}`}>
        <div className={styles.cover}>
          {service.cover_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={service.cover_url} alt="" className={styles.coverImage} />
          ) : (
            <span className="av-muted">{service.category.name}</span>
          )}
        </div>

        <div className="av-stack-sm">
          <div className="av-row av-wrap">
            <Badge tone="neutral" size="sm">
              {service.category.name}
            </Badge>
            {service.is_owner ? (
              <Badge tone={service.status === 'active' ? 'success' : 'warning'} size="sm">
                {SERVICE_STATUS[service.status] ?? service.status}
              </Badge>
            ) : null}
          </div>
          <h1 className={styles.title}>{service.title}</h1>
          <div className={styles.meta}>
            {service.rating_avg ? (
              <span className={styles.rating}>
                <IconStarFilled size={14} />
                {service.rating_avg.toFixed(1)} ({service.rating_count})
              </span>
            ) : (
              <span>Без отзывов</span>
            )}
            <span>{plural(service.orders_count, 'заказ', 'заказа', 'заказов')}</span>
            <span>
              <IconClock size={13} /> {days(service.delivery_days)}
            </span>
            {service.revisions ? (
              <span>
                <IconRefresh size={13} /> {plural(service.revisions, 'правка', 'правки', 'правок')}
              </span>
            ) : null}
          </div>
        </div>

        {service.is_owner ? (
          <Card>
            <div className="av-row av-wrap">
              <ButtonLink href={`/services/${service.id}/edit`} variant="secondary" size="sm">
                Редактировать
              </ButtonLink>
              <ButtonLink href="/services/mine" variant="ghost" size="sm">
                Все мои услуги
              </ButtonLink>
            </div>
          </Card>
        ) : null}

        <Card>
          <h2 className={styles.sectionTitle}>Что входит</h2>
          <div className={styles.tiers}>
            {service.tiers.map((item, index) => (
              <button
                key={item.id ?? index}
                type="button"
                className={[styles.tier, index === tier ? styles.tierActive : ''].join(' ')}
                onClick={() => setTier(index)}
                aria-pressed={index === tier}
              >
                <span className={styles.tierName}>{item.name}</span>
                <span className={styles.tierPrice}>{item.price_display ?? money(item.price_minor, service.currency)}</span>
                <span className={styles.tierFacts}>
                  <span>Срок: {days(item.delivery_days)}</span>
                  <span>Правок: {item.revisions}</span>
                </span>
                {item.includes?.length ? (
                  <ul className={styles.includes}>
                    {item.includes.map((line) => (
                      <li key={line}>
                        <IconCheck size={14} /> {line}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </button>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className={styles.sectionTitle}>Описание</h2>
          <p className={styles.description}>{service.description}</p>
        </Card>

        {service.skills?.length ? (
          <Card>
            <h2 className={styles.sectionTitle}>Навыки</h2>
            <div className={styles.tags}>
              {service.skills.map((skill) => (
                <Tag key={skill.slug}>{skill.name}</Tag>
              ))}
            </div>
          </Card>
        ) : null}

        <Card>
          <h2 className={styles.sectionTitle}>Исполнитель</h2>
          <Link href={`/developers/${service.seller.username}`} className={styles.seller}>
            <Avatar src={service.seller.photo_url} name={service.seller.full_name} size={48} />
            <div className="av-grow">
              <p className="av-strong">{service.seller.full_name}</p>
              <p className="av-small av-muted">
                {service.seller.professional_title ?? 'Исполнитель'}
                {service.seller.rating_avg ? ` · ${service.seller.rating_avg.toFixed(1)} ★` : ''}
                {service.seller.projects_completed
                  ? ` · ${plural(service.seller.projects_completed, 'заказ', 'заказа', 'заказов')}`
                  : ''}
              </p>
            </div>
          </Link>
        </Card>

        {session && !service.is_owner ? (
          <Button variant="ghost" size="sm" onClick={() => setReporting(true)}>
            Пожаловаться на услугу
          </Button>
        ) : null}

        {!service.is_owner ? (
          <div className={styles.orderBar}>
            <div>
              <span className="av-xs av-muted">{selected?.name}</span>
              <p className={styles.orderPrice}>
                {selected?.price_display ?? money(selected?.price_minor ?? 0, service.currency)}
              </p>
            </div>
            {isClient ? (
              <Button size="lg" disabled={!service.can_order} onClick={() => setOrdering(true)}>
                Заказать
              </Button>
            ) : session ? (
              <span className="av-small av-muted">Заказывать услуги может заказчик</span>
            ) : (
              <ButtonLink href={`/login?next=/services/${service.id}`} size="lg">
                Войти и заказать
              </ButtonLink>
            )}
          </div>
        ) : null}
      </main>

      <OrderSheet
        open={ordering}
        service={service}
        tier={tier}
        onClose={() => setOrdering(false)}
      />
      <ReportSheet
        open={reporting}
        subjectType="service"
        subjectId={service.id}
        title={service.title}
        onClose={() => setReporting(false)}
      />
      <BottomNav />
    </>
  );
}

function OrderSheet({
  open,
  service,
  tier,
  onClose,
}: {
  open: boolean;
  service: Service;
  tier: number;
  onClose: () => void;
}) {
  const router = useRouter();
  const [brief, setBrief] = useState('');
  const [visibility, setVisibility] = useState('range');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [fields, setFields] = useState<Record<string, string>>({});

  const selected = service.tiers[tier] ?? service.tiers[0];

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Заказать услугу"
      description={`${service.title} · ${selected?.name}`}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button
            loading={busy}
            disabled={brief.trim().length < 20}
            onClick={async () => {
              setBusy(true);
              setError('');
              setFields({});
              try {
                const contract = await post<{ id: string }>(`/services/${service.id}/order`, {
                  tier: tier + 1,
                  brief: brief.trim(),
                  price_visibility: visibility,
                });
                router.push(`/contracts/${contract.id}`);
              } catch (failure) {
                if (failure instanceof ApiFailure) {
                  setFields(failure.fields);
                  setError(Object.keys(failure.fields).length ? '' : failure.message);
                } else {
                  setError('Не удалось оформить заказ. Попробуйте ещё раз.');
                }
              } finally {
                setBusy(false);
              }
            }}
          >
            Оформить заказ
          </Button>
        </>
      }
    >
      <div className="av-stack">
        {error ? (
          <p className={styles.alert} role="alert">
            {error}
          </p>
        ) : null}

        <Card>
          <div className="av-row-between">
            <span className="av-muted">Пакет</span>
            <strong>{selected?.name}</strong>
          </div>
          <div className="av-row-between">
            <span className="av-muted">Цена</span>
            <strong>{selected?.price_display ?? money(selected?.price_minor ?? 0, service.currency)}</strong>
          </div>
          <div className="av-row-between">
            <span className="av-muted">Срок</span>
            <strong>{days(selected?.delivery_days ?? service.delivery_days)}</strong>
          </div>
        </Card>

        <Textarea
          label="Что нужно сделать"
          placeholder="Опишите задачу: для чего, какие материалы у вас есть, чего точно не надо делать."
          hint="Не меньше 20 символов. Это техническое задание — исполнитель начнёт по нему."
          max={4000}
          rows={7}
          value={brief}
          error={fields.brief}
          onChange={(event) => setBrief(event.target.value)}
        />

        <Select
          label="Показывать стоимость в профиле исполнителя как"
          value={visibility}
          onChange={(event) => setVisibility(event.target.value)}
        >
          <option value="public">Точная сумма</option>
          <option value="range">Диапазон</option>
          <option value="hidden">Не показывать</option>
          <option value="private">«Закрытая сделка»</option>
        </Select>

        <p className="av-small av-muted">
          Сейчас ничего не списывается: после оформления откроется сделка, где оплата резервируется по
          этапу, а исполнитель начинает работу после подтверждения.
        </p>
      </div>
    </Sheet>
  );
}
