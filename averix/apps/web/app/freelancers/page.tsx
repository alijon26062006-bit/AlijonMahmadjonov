'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import styles from '../catalogue.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { BottomNav } from '@/components/nav/BottomNav';
import { FreelancerCard } from '@/components/domain/FreelancerCard';
import { Button } from '@/components/ui/Button';
import { ChoiceChip, Input, Select } from '@/components/ui/Field';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconSearch } from '@/components/ui/Icon';
import { list } from '@/lib/api';
import { plural } from '@/lib/format';
import { AVAILABILITY, SECTORS } from '@/lib/labels';
import type { FreelancerCard as FreelancerCardType } from '@/lib/types';

const SORTS = [
  { key: 'relevance', label: 'По совпадению' },
  { key: 'rating', label: 'По рейтингу' },
  { key: 'rate_asc', label: 'Ставка: дешевле' },
  { key: 'rate_desc', label: 'Ставка: дороже' },
  { key: 'newest', label: 'Новые' },
  { key: 'active', label: 'Недавно были онлайн' },
];

function Catalogue() {
  const params = useSearchParams();
  const router = useRouter();

  const [sector, setSector] = useState(params.get('sector') ?? '');
  const [text, setText] = useState(params.get('q') ?? '');
  const [availability, setAvailability] = useState('');
  const [verified, setVerified] = useState(false);
  const [sort, setSort] = useState('relevance');
  const [cards, setCards] = useState<FreelancerCardType[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [failed, setFailed] = useState(false);

  const load = useCallback(
    async (nextOffset: number, append: boolean) => {
      setFailed(false);
      if (!append) setCards(null);
      const query = new URLSearchParams();
      if (sector) query.set('sector', sector);
      if (text.trim()) query.set('q', text.trim());
      if (availability) query.set('availability', availability);
      if (verified) query.set('verified', 'true');
      if (sort) query.set('sort', sort);
      query.set('offset', String(nextOffset));
      query.set('limit', '20');
      try {
        const response = await list<FreelancerCardType[]>(`/freelancers?${query.toString()}`);
        setCards((current) => (append && current ? [...current, ...(response.data ?? [])] : response.data ?? []));
        setTotal(Number(response.meta?.total ?? 0));
        setOffset(nextOffset);
      } catch {
        setFailed(true);
        if (!append) setCards([]);
      }
    },
    [sector, text, availability, verified, sort],
  );

  useEffect(() => {
    void load(0, false);
    // Строка поиска отправляется по кнопке, остальные фильтры — сразу.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sector, availability, verified, sort]);

  return (
    <>
      <TopBar />
      <main id="main" className={`av-page ${styles.shell}`}>
        <h1 className={styles.heading}>Исполнители</h1>
        <p className={styles.lede}>
          Дизайнеры, авторы, разработчики, маркетологи, монтажёры, бухгалтеры — все, кто работает
          удалённо.
        </p>

        <div className={styles.filters}>
          <form
            className={styles.filterRow}
            onSubmit={(event) => {
              event.preventDefault();
              void load(0, false);
              const query = new URLSearchParams();
              if (sector) query.set('sector', sector);
              if (text.trim()) query.set('q', text.trim());
              router.replace(`/freelancers${query.toString() ? `?${query}` : ''}`);
            }}
          >
            <Input
              label="Кого ищете"
              placeholder="Логотип, лендинг, монтаж, Python…"
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
            <ChoiceChip selected={sector === ''} onToggle={() => setSector('')}>
              Все направления
            </ChoiceChip>
            {SECTORS.map((item) => (
              <ChoiceChip key={item.slug} selected={sector === item.slug} onToggle={() => setSector(item.slug)}>
                {item.name}
              </ChoiceChip>
            ))}
          </div>

          <div className={styles.filterRow}>
            <Select label="Занятость" value={availability} onChange={(event) => setAvailability(event.target.value)}>
              <option value="">Любая</option>
              {Object.entries(AVAILABILITY).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </Select>
            <Select label="Сортировка" value={sort} onChange={(event) => setSort(event.target.value)}>
              {SORTS.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.label}
                </option>
              ))}
            </Select>
            <label className="av-row" style={{ alignItems: 'center', gap: 'var(--av-space-2)' }}>
              <input type="checkbox" checked={verified} onChange={(event) => setVerified(event.target.checked)} />
              <span className="av-small">Только с подтверждённой личностью</span>
            </label>
          </div>
        </div>

        {cards === null ? (
          <SkeletonList count={4} />
        ) : cards.length === 0 ? (
          <EmptyState
            tone={failed ? 'error' : undefined}
            icon={<IconSearch size={20} />}
            title={failed ? 'Не удалось загрузить каталог' : 'Никого не нашли'}
            description={
              failed
                ? 'Попробуйте ещё раз через минуту.'
                : 'Попробуйте другое направление или более общий запрос — например, «дизайн» вместо «дизайн упаковки чая».'
            }
            action={
              <Button variant="secondary" onClick={() => void load(0, false)}>
                Повторить
              </Button>
            }
          />
        ) : (
          <>
            <p className={styles.count}>
              {plural(total, 'исполнитель', 'исполнителя', 'исполнителей')}
            </p>
            <div className={styles.list}>
              {cards.map((card) => (
                <FreelancerCard key={card.user_id} card={card} />
              ))}
            </div>
            {cards.length < total ? (
              <div className={styles.more}>
                <Button variant="secondary" onClick={() => void load(offset + 20, true)}>
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

export default function FreelancersPage() {
  return (
    <Suspense fallback={null}>
      <Catalogue />
    </Suspense>
  );
}
