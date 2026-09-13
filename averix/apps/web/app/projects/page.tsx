'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import styles from '../catalogue.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { BottomNav } from '@/components/nav/BottomNav';
import { Card } from '@/components/ui/Card';
import { Badge, Tag } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ChoiceChip, Input, Select } from '@/components/ui/Field';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconSearch } from '@/components/ui/Icon';
import { list } from '@/lib/api';
import { plural, timeAgo } from '@/lib/format';
import { SECTORS } from '@/lib/labels';
import { useSession } from '@/lib/session';
import type { ProjectHit } from '@/lib/types';

const SORTS = [
  { key: 'newest', label: 'Сначала новые' },
  { key: 'budget', label: 'Сначала дорогие' },
  { key: 'proposals', label: 'Меньше откликов' },
];

const PAGE = 24;

/**
 * Открытые заказы — публичный каталог.
 *
 * Его видно без аккаунта: человек должен понять, есть ли здесь работа для
 * него, до того как заводить логин. Регистрация встречает его на действии —
 * на кнопке «Откликнуться» внутри заказа, — а не на входе в каталог.
 */
function Catalogue() {
  const params = useSearchParams();
  const router = useRouter();
  const { session } = useSession();

  const [category, setCategory] = useState(params.get('category') ?? '');
  const [text, setText] = useState(params.get('q') ?? '');
  const [sort, setSort] = useState('newest');
  const [hits, setHits] = useState<ProjectHit[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [failed, setFailed] = useState(false);

  const load = useCallback(
    async (nextOffset: number, append: boolean) => {
      setFailed(false);
      if (!append) setHits(null);
      const query = new URLSearchParams();
      if (category) query.set('category', category);
      if (text.trim()) query.set('q', text.trim());
      query.set('sort', sort);
      query.set('offset', String(nextOffset));
      query.set('limit', String(PAGE));
      try {
        const response = await list<ProjectHit[]>(`/projects/browse?${query.toString()}`);
        setHits((current) => (append && current ? [...current, ...(response.data ?? [])] : response.data ?? []));
        setTotal(Number(response.meta?.total ?? 0));
        setOffset(nextOffset);
      } catch {
        setFailed(true);
        if (!append) setHits([]);
      }
    },
    [category, text, sort],
  );

  useEffect(() => {
    void load(0, false);
    // Строка поиска отправляется по кнопке, остальные фильтры — сразу.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, sort]);

  return (
    <>
      <TopBar />
      <main id="main" className={`av-page ${styles.shell}`}>
        <h1 className={styles.heading}>Открытые заказы</h1>
        <p className={styles.lede}>
          Всё, что сейчас ищут заказчики: от логотипа и текста до Telegram-бота и годового
          отчёта. Смотреть можно без регистрации — она нужна, только чтобы откликнуться.
        </p>

        <div className={styles.filters}>
          <form
            className={styles.filterRow}
            onSubmit={(event) => {
              event.preventDefault();
              void load(0, false);
              const query = new URLSearchParams();
              if (category) query.set('category', category);
              if (text.trim()) query.set('q', text.trim());
              router.replace(`/projects${query.toString() ? `?${query}` : ''}`);
            }}
          >
            <Input
              label="Что ищете"
              placeholder="Лендинг, логотип, монтаж, бот…"
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
            <ChoiceChip selected={category === ''} onToggle={() => setCategory('')}>
              Все направления
            </ChoiceChip>
            {SECTORS.map((item) => (
              <ChoiceChip key={item.slug} selected={category === item.slug} onToggle={() => setCategory(item.slug)}>
                {item.name}
              </ChoiceChip>
            ))}
          </div>

          <div className={styles.filterRow}>
            <Select label="Сортировка" value={sort} onChange={(event) => setSort(event.target.value)}>
              {SORTS.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.label}
                </option>
              ))}
            </Select>
          </div>
        </div>

        {hits === null ? (
          <SkeletonList count={4} />
        ) : hits.length === 0 ? (
          <EmptyState
            tone={failed ? 'error' : undefined}
            icon={<IconSearch size={20} />}
            title={failed ? 'Не удалось загрузить заказы' : 'Открытых заказов не нашлось'}
            description={
              failed
                ? 'Попробуйте ещё раз через минуту.'
                : 'Попробуйте другое направление или более общий запрос — например, «тексты» вместо «описание карточек для маркетплейса».'
            }
            action={
              <Button variant="secondary" onClick={() => void load(0, false)}>
                Повторить
              </Button>
            }
          />
        ) : (
          <>
            <p className={styles.count}>{plural(total, 'открытый заказ', 'открытых заказа', 'открытых заказов')}</p>
            <div className={styles.list}>
              {hits.map((hit) => (
                <Link key={hit.id} href={`/projects/${hit.slug}`} className={styles.cardLink}>
                  <Card>
                    <div className={styles.cardHead}>
                      <Badge tone="neutral" size="sm">
                        {hit.category_name}
                      </Badge>
                      <span className={styles.cardBudget}>{hit.budget_display}</span>
                    </div>
                    <h2 className={styles.cardTitle}>{hit.title}</h2>
                    {hit.excerpt ? <p className={styles.cardExcerpt}>{hit.excerpt}</p> : null}
                    {hit.skills?.length ? (
                      <div className={styles.cardTags}>
                        {hit.skills.slice(0, 6).map((skill) => (
                          <Tag key={skill}>{skill}</Tag>
                        ))}
                      </div>
                    ) : null}
                    <p className={styles.cardMeta}>
                      {hit.published_at ? `Опубликован ${timeAgo(hit.published_at)}` : 'Только что'} ·{' '}
                      {plural(hit.proposals_count, 'отклик', 'отклика', 'откликов')}
                    </p>
                  </Card>
                </Link>
              ))}
            </div>
            {hits.length < total ? (
              <div className={styles.more}>
                <Button variant="secondary" onClick={() => void load(offset + PAGE, true)}>
                  Показать ещё
                </Button>
              </div>
            ) : null}
          </>
        )}

        {!session ? (
          <p className={styles.invite}>
            Хотите брать такие заказы? <Link href="/register">Создайте аккаунт</Link> — после
            регистрации вы выберете, работать или заказывать.
          </p>
        ) : null}
      </main>
      <BottomNav />
    </>
  );
}

export default function ProjectsCataloguePage() {
  return (
    <Suspense fallback={null}>
      <Catalogue />
    </Suspense>
  );
}
