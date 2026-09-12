'use client';

import styles from './PortfolioGrid.module.css';
import { Badge, Tag } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { IconExternal, IconShield } from '@/components/ui/Icon';
import { shortDate } from '@/lib/format';
import type { PortfolioCard } from '@/lib/types';

/**
 * The portfolio grid.
 *
 * AVERIX-verified contracts and self-declared portfolio work sit in the same
 * grid but are never dressed the same: the verified ones carry the platform's
 * own mark, and nothing a developer types can produce it.
 */
export function PortfolioGrid({
  items,
  username,
  onPreview,
}: {
  items: PortfolioCard[];
  username: string;
  onPreview: (slug: string) => void;
}) {
  return (
    <div className={styles.grid}>
      {items.map((item) => (
        <article key={item.id} className={styles.card}>
          <div className={styles.cover} style={{ background: item.cover?.placeholder || undefined }}>
            {item.cover?.url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={item.cover.url}
                alt=""
                className={styles.coverImage}
                loading="lazy"
                srcSet={item.cover.variants
                  ?.filter((variant) => variant.format === 'webp')
                  .map((variant) => `${variant.url} ${variant.width}w`)
                  .join(', ')}
                sizes="(max-width: 768px) 100vw, 380px"
              />
            ) : null}
            {item.kind === 'averix_verified' ? (
              <span className={styles.verified}>
                <IconShield size={13} />
                AVERIX verified
              </span>
            ) : null}
          </div>

          <div className={styles.body}>
            <header className={styles.header}>
              <h3 className={styles.title}>{item.title}</h3>
              {item.value_display ? (
                <span className={styles.value}>{item.value_display}</span>
              ) : null}
            </header>

            {item.excerpt ? <p className={`${styles.excerpt} av-clamp-2`}>{item.excerpt}</p> : null}

            {item.skills?.length ? (
              <div className={styles.tags}>
                {item.skills.map((skill) => (
                  <Tag key={skill.slug}>{skill.name}</Tag>
                ))}
              </div>
            ) : null}

            <footer className={styles.footer}>
              <span className="av-xs av-faint">
                {item.completed_on ? shortDate(item.completed_on) : ''}
                {item.kind === 'portfolio' ? ' · self-declared' : ''}
              </span>
              {item.can_preview ? (
                <Button
                  size="sm"
                  variant="secondary"
                  icon={<IconExternal size={15} />}
                  onClick={() => onPreview(item.slug)}
                >
                  Live preview
                </Button>
              ) : item.demo_status === 'nda' ? (
                <Badge tone="neutral" size="sm">
                  Under NDA
                </Badge>
              ) : item.project_host ? (
                <Badge tone="neutral" size="sm">
                  {item.project_host}
                </Badge>
              ) : null}
            </footer>
          </div>
        </article>
      ))}
    </div>
  );
}
