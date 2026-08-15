/** Главная: направления и категории. */
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { Direction } from '../api/types';
import { CATEGORY_ICON, DIRECTION_ICON, Icon } from '../components/icons';
import { CardSkeletons } from '../components/ui';

export default function HomePage() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery<{ directions: Direction[] }>({
    queryKey: ['categories'],
    queryFn: () => api('/api/categories'),
    staleTime: 10 * 60_000,
  });

  return (
    <div className="fade-in">
      <div className="section">
        <h1 className="section-title">Что ищете?</h1>
        <div className="searchbar">
          <input placeholder="Поиск: Camry, квартира, дисплей…"
                 onKeyDown={(e) => {
                   if (e.key === 'Enter') {
                     const q = (e.target as HTMLInputElement).value.trim();
                     navigate(q ? `/catalog?q=${encodeURIComponent(q)}` : '/catalog');
                   }
                 }} />
        </div>
      </div>

      {isLoading && <div className="section"><CardSkeletons n={4} /></div>}

      {data?.directions.map((d) => {
        const dir = DIRECTION_ICON[d.slug] ?? DIRECTION_ICON.parts;
        return (
          <section key={d.slug} className="dir-block">
            <div className="dir-head">
              <span className={`dir-ico ${dir.tone}`}>
                <Icon name={dir.icon} size={17} strokeWidth={2.2} />
              </span>
              {d.title}
            </div>
            <div className="cat-grid">
              {d.categories.map((c) => (
                <Link key={c.slug} to={`/catalog?category=${c.slug}`} className="cat-tile">
                  <span className={`icon-wrap ${dir.tone}`}>
                    <Icon name={CATEGORY_ICON[c.slug] ?? dir.icon} size={21} />
                  </span>
                  {c.title}
                </Link>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
