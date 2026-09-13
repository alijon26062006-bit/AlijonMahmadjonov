'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import styles from '../catalogue.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { BottomNav } from '@/components/nav/BottomNav';
import { ServiceCard } from '@/components/domain/ServiceCard';
import { Button, ButtonLink } from '@/components/ui/Button';
import { ChoiceChip, Input, Select } from '@/components/ui/Field';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconLayers, IconSearch } from '@/components/ui/Icon';
import { get, list } from '@/lib/api';
import { plural } from '@/lib/format';
import { SECTORS } from '@/lib/labels';
import { useSession } from '@/lib/session';
import type { Category, ServiceCard as ServiceCardType } from '@/lib/types';

const SORTS = [
  { key: 'relevance', label: 'По совпадению' },
  { key: 'popular', label: 'Популярные' },
  { key: 'rating', label: 'По рейтингу' },
  { key: 'price_asc', label: 'Сначала дешевле' },
  { key: 'price_desc', label: 'Сначала дороже' },
  { key: 'newest', label: 'Новые' },
];

function Catalogue() {
  const params = useSearchParams();
  const { session } = useSession();

  const [sector, setSector] = useState(params.get('sector') ?? '');
  const [category, setCategory] = useState(params.get('category') ?? '');
  const [text, setText] = useState(params.get('q') ?? '');
  const [sort, setSort] = useState('relevance');
  const [maxPrice, setMaxPrice] = useState('');
  const [delivery, setDelivery] = useState('');
  const [tree, setTree] = useState<Category[]>([]);
  const [cards, setCards] = useState<ServiceCardType[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    get<Category[]>('/taxonomy/categories')
      .then(setTree)
      .catch(() => undefined);
  }, []);

  const load = useCallback(
    async (nextOffset: number, append: boolean) => {
      setFailed(false);
      if (!append) setCards(null);
      const query = new URLSearchParams();
      if (category) query.set('category', category);
      else if (sector) query.set('category', sector);
      if (text.trim()) query.set('q', text.trim());
      if (sort) query.set('sort', sort);
      if (maxPrice.trim()) query.set('max', String(Math.round(Number(maxPrice) * 100)));
      if (delivery.trim()) query.set('delivery', delivery.trim());
      query.set('offset', String(nextOffset));
      query.set('limit', '24');
      try {
        const response = await list<ServiceCardType[]>(`/services?${query.toString()}`);
        setCards((current) => (append && current ? [...current, ...(response.data ?? [])] : response.data ?? []));
        setTotal(Number(response.meta?.total ?? 0));
        setOffset(nextOffset);
      } catch {
        setFailed(true);
        if (!append) setCards([]);
      }
    },
    [sector, category, text, sort, maxPrice, delivery],
  );

  useEffect(() => {
    void load(0, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sector, category, sort]);

  const subcategories = tree.find((node) => node.slug === sector)?.children ?? [];

  return (
    <>
      <TopBar
        action={
          session?.active_role === 'developer' ? (
            <ButtonLink href="/services/new" size="sm">
              Создать услугу
            </ButtonLink>
          ) : undefined
        }
      />
      <main id="main" className={`av-page ${styles.shell}`}>
        <h1 className={styles.heading}>Готовые услуги</h1>
        <p className={styles.lede}>
          Фиксированная цена и срок: выбираете пакет, описываете задачу — и работа начинается без
          переговоров.
        </p>

        <div className={styles.filters}>
          <form
            className={styles.filterRow}
            onSubmit={(event) => {
              event.preventDefault();
              void load(0, false);
            }}
          >
            <Input
              label="Что нужно"
              placeholder="Логотип, лендинг, монтаж ролика…"
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <Button type="submit" icon={<IconSearch size={16} />}>
                Найти
              </Button>
            </div>
          </form>

          <div className={styles.chips}>
            <ChoiceChip
              selected={sector === ''}
              onToggle={() => {
                setSector('');
                setCategory('');
              }}
            >
              Все направления
            </ChoiceChip>
            {SECTORS.map((item) => (
              <ChoiceChip
                key={item.slug}
                selected={sector === item.slug}
                onToggle={() => {
                  setSector(item.slug);
                  setCategory('');
                }}
              >
                {item.name}
              </ChoiceChip>
            ))}
          </div>

          {subcategories.length ? (
            <div className={styles.chips}>
              {subcategories.map((item) => (
                <ChoiceChip
                  key={item.slug}
                  selected={category === item.slug}
                  onToggle={() => setCategory(category === item.slug ? '' : item.slug)}
                >
                  {item.name}
                </ChoiceChip>
              ))}
            </div>
          ) : null}

          <div className={styles.filterRow}>
            <Input
              label="Цена до"
              optional
              inputMode="numeric"
              value={maxPrice}
              onChange={(event) => setMaxPrice(event.target.value)}
            />
            <Input
              label="Срок, дней до"
              optional
              inputMode="numeric"
              value={delivery}
              onChange={(event) => setDelivery(event.target.value)}
            />
            <Select label="Сортировка" value={sort} onChange={(event) => setSort(event.target.value)}>
              {SORTS.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.label}
                </option>
              ))}
            </Select>
          </div>
        </div>

        {cards === null ? (
          <SkeletonList count={4} />
        ) : cards.length === 0 ? (
          <EmptyState
            tone={failed ? 'error' : undefined}
            icon={<IconLayers size={20} />}
            title={failed ? 'Не удалось загрузить услуги' : 'Услуг по запросу нет'}
            description={
              failed
                ? 'Попробуйте ещё раз через минуту.'
                : 'Попробуйте другое направление — или разместите заказ, и исполнители откликнутся сами.'
            }
            action={<ButtonLink href="/projects/new">Разместить заказ</ButtonLink>}
          />
        ) : (
          <>
            <p className={styles.count}>{plural(total, 'услуга', 'услуги', 'услуг')}</p>
            <div className={styles.grid}>
              {cards.map((card) => (
                <ServiceCard key={card.id} service={card} />
              ))}
            </div>
            {cards.length < total ? (
              <div className={styles.more}>
                <Button variant="secondary" onClick={() => void load(offset + 24, true)}>
                  Показать ещё
                </Button>
              </div>
            ) : null}
          </>
        )}
      </main>
      <BottomNav />
    </>
  );
}

export default function ServicesPage() {
  return (
    <Suspense fallback={null}>
      <Catalogue />
    </Suspense>
  );
}
