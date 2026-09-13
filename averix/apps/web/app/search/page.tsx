'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import styles from '../catalogue.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { BottomNav } from '@/components/nav/BottomNav';
import { Card } from '@/components/ui/Card';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Input } from '@/components/ui/Field';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { FreelancerCard } from '@/components/domain/FreelancerCard';
import { ServiceCard } from '@/components/domain/ServiceCard';
import { IconSearch } from '@/components/ui/Icon';
import { get } from '@/lib/api';
import { plural, timeAgo } from '@/lib/format';
import type { SearchResults } from '@/lib/types';

function Search() {
  const params = useSearchParams();
  const router = useRouter();
  const initial = params.get('q') ?? '';
  const [text, setText] = useState(initial);
  const [results, setResults] = useState<SearchResults | null>(null);
  const [searching, setSearching] = useState(false);

  const run = useCallback(async (query: string) => {
    if (!query.trim()) {
      setResults(null);
      return;
    }
    setSearching(true);
    try {
      setResults(await get<SearchResults>(`/search?q=${encodeURIComponent(query.trim())}`));
    } catch {
      setResults(null);
    } finally {
      setSearching(false);
    }
  }, []);

  useEffect(() => {
    if (initial) void run(initial);
  }, [initial, run]);

  const nothing =
    results &&
    results.freelancers.length === 0 &&
    (results.services ?? []).length === 0 &&
    results.projects.length === 0;

  return (
    <>
      <TopBar back title="Поиск" />
      <main id="main" className={`av-page av-stack ${styles.shell}`}>
        <form
          className={styles.filterRow}
          onSubmit={(event) => {
            event.preventDefault();
            router.replace(`/search?q=${encodeURIComponent(text.trim())}`);
            void run(text);
          }}
        >
          <Input
            label="Поиск по AVERIX"
            placeholder="Исполнители, услуги, заказы"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <div style={{ display: 'flex', alignItems: 'flex-end' }}>
            <Button type="submit" icon={<IconSearch size={16} />} loading={searching}>
              Найти
            </Button>
          </div>
        </form>

        {searching && !results ? <SkeletonList count={3} /> : null}

        {nothing ? (
          <EmptyState
            icon={<IconSearch size={20} />}
            title="Ничего не нашли"
            description="Попробуйте более общий запрос: одно-два слова работают лучше длинной фразы."
          />
        ) : null}

        {results && !nothing ? (
          <>
            {results.freelancers.length ? (
              <section className="av-stack-sm">
                <div className="av-row-between">
                  <h2 className="av-lg av-strong">Исполнители</h2>
                  <Link href={`/freelancers?q=${encodeURIComponent(results.query)}`} className="av-small">
                    Все {results.totals?.freelancers ?? results.freelancers.length}
                  </Link>
                </div>
                {results.freelancers.map((card) => (
                  <FreelancerCard key={card.user_id} card={card} />
                ))}
              </section>
            ) : null}

            {(results.services ?? []).length ? (
              <section className="av-stack-sm">
                <div className="av-row-between">
                  <h2 className="av-lg av-strong">Услуги</h2>
                  <Link href={`/services?q=${encodeURIComponent(results.query)}`} className="av-small">
                    Все {results.totals?.services ?? (results.services ?? []).length}
                  </Link>
                </div>
                <div className={styles.grid}>
                  {(results.services ?? []).map((service) => (
                    <ServiceCard key={service.id} service={service} />
                  ))}
                </div>
              </section>
            ) : null}

            {results.projects.length ? (
              <section className="av-stack-sm">
                <h2 className="av-lg av-strong">Заказы</h2>
                {results.projects.map((project) => (
                  <Card key={project.id} href={`/projects/${project.slug}`}>
                    <p className="av-strong">{project.title}</p>
                    <p className="av-small av-muted">
                      {project.category_name} · {project.budget_display} ·{' '}
                      {plural(project.proposals_count, 'отклик', 'отклика', 'откликов')}
                      {project.published_at ? ` · ${timeAgo(project.published_at)}` : ''}
                    </p>
                  </Card>
                ))}
              </section>
            ) : null}
          </>
        ) : null}

        {!results && !searching ? (
          <div className="av-stack-sm">
            <p className="av-muted">Что ищем? Поиск смотрит по исполнителям, услугам и открытым заказам сразу.</p>
            <div className="av-row av-wrap">
              <ButtonLink href="/freelancers" variant="secondary" size="sm">
                Каталог исполнителей
              </ButtonLink>
              <ButtonLink href="/services" variant="secondary" size="sm">
                Готовые услуги
              </ButtonLink>
            </div>
          </div>
        ) : null}
      </main>
      <BottomNav />
    </>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={null}>
      <Search />
    </Suspense>
  );
}
