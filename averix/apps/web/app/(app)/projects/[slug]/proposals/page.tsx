'use client';

import { use, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import styles from './proposals.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Tabs } from '@/components/ui/Tabs';
import { Card } from '@/components/ui/Card';
import { Avatar } from '@/components/ui/Avatar';
import { Badge, Tag } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { MatchExplainer } from '@/components/domain/MatchExplainer';
import { IconCheck, IconShield, IconStarFilled, IconUser } from '@/components/ui/Icon';
import { ApiFailure, get, post } from '@/lib/api';
import { days, money, plural, timeAgo } from '@/lib/format';
import type { Project, ProposalCard } from '@/lib/types';

const SORTS = [
  { key: 'recommended', label: 'Рекомендуем' },
  { key: 'match', label: 'Совпадение' },
  { key: 'newest', label: 'Новые' },
  { key: 'price', label: 'Цена' },
  { key: 'delivery', label: 'Быстрее' },
  { key: 'rating', label: 'Рейтинг' },
];

export default function ProposalsPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [proposals, setProposals] = useState<ProposalCard[] | null>(null);
  const [sort, setSort] = useState('recommended');
  const [hiring, setHiring] = useState<ProposalCard | null>(null);

  const load = useCallback(
    async (nextSort: string) => {
      setProposals(null);
      const found = project ?? (await get<Project>(`/projects/${slug}`));
      setProject(found);
      try {
        setProposals(await get<ProposalCard[]>(`/projects/${found.id}/proposals?sort=${nextSort}`));
      } catch {
        setProposals([]);
      }
    },
    [slug, project],
  );

  useEffect(() => {
    void load(sort);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load is stable enough here
  }, [sort, slug]);

  return (
    <>
      <TopBar back={`/dashboard`} title="Отклики" />
      <div className="av-page av-stack">
        <header>
          <h1 className={styles.title}>{project?.title ?? 'Отклики'}</h1>
          <p className="av-muted av-small">
            {proposals ? plural(proposals.length, 'отклик', 'отклика', 'откликов') : 'Загружаем отклики'}
            {project ? ` · ${project.budget.display}` : ''}
          </p>
        </header>

        <Tabs items={SORTS} active={sort} onChange={setSort} ariaLabel="Сортировка откликов" />

        {proposals === null ? (
          <SkeletonList count={3} />
        ) : proposals.length === 0 ? (
          <EmptyState
            icon={<IconUser size={20} />}
            title="Откликов пока нет"
            description="Подходящие исполнители появятся здесь. Большинство заказов получают первый отклик в течение дня."
          />
        ) : (
          <div className="av-stack-sm">
            {proposals.map((proposal) => (
              <Card key={proposal.id}>
                <div className={styles.head}>
                  <Link href={`/developers/${proposal.developer.username}`} className={styles.person}>
                    <Avatar
                      src={proposal.developer.photo_url}
                      name={proposal.developer.full_name}
                      size={48}
                      verified={proposal.developer.identity_verified}
                    />
                    <div className="av-grow">
                      <p className="av-strong">{proposal.developer.full_name}</p>
                      <p className="av-small av-muted">
                        {proposal.developer.professional_title ?? 'Исполнитель'}
                        {proposal.developer.country_code ? ` · ${proposal.developer.country_code}` : ''}
                      </p>
                      <div className={styles.stats}>
                        {proposal.developer.rating_avg ? (
                          <span className={styles.rating}>
                            <IconStarFilled size={13} />
                            {proposal.developer.rating_avg.toFixed(1)}
                          </span>
                        ) : null}
                        {proposal.developer.projects_completed ? (
                          <span>
                            {plural(proposal.developer.projects_completed, 'заказ', 'заказа', 'заказов')} на AVERIX
                          </span>
                        ) : (
                          <span className="av-faint">Новичок на AVERIX</span>
                        )}
                        {proposal.developer.identity_verified ? (
                          <span className={styles.verified}>
                            <IconShield size={13} /> Проверен
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </Link>

                  <div className={styles.quote}>
                    <span className={styles.amount}>{proposal.amount_display}</span>
                    <span className="av-small av-muted">{days(proposal.delivery_days)}</span>
                    {proposal.shortlisted_at ? (
                      <Badge tone="brand" size="sm">
                        В шорт-листе
                      </Badge>
                    ) : null}
                  </div>
                </div>

                {proposal.match_score !== undefined ? (
                  <div className={styles.match}>
                    <MatchExplainer score={proposal.match_score} highlights={proposal.match_highlights} />
                  </div>
                ) : null}

                {proposal.preview ? (
                  <p className={`${styles.excerpt} av-clamp-3`}>{proposal.preview}</p>
                ) : null}

                {proposal.developer.skills?.length ? (
                  <div className={styles.tags}>
                    {proposal.developer.skills.map((skill) => (
                      <Tag key={skill}>{skill}</Tag>
                    ))}
                  </div>
                ) : null}

                {proposal.top_evidence ? (
                  <div className={styles.evidence}>
                    <Badge
                      tone={proposal.top_evidence.kind === 'averix_verified' ? 'verified' : 'neutral'}
                      size="sm"
                      icon={
                        proposal.top_evidence.kind === 'averix_verified' ? (
                          <IconShield size={12} />
                        ) : undefined
                      }
                    >
                      {proposal.top_evidence.kind === 'averix_verified'
                        ? 'Подтверждённая работа на AVERIX'
                        : 'Из портфолио'}
                    </Badge>
                    <p className="av-small av-strong">{proposal.top_evidence.title}</p>
                    {proposal.top_evidence.technologies?.length ? (
                      <p className="av-xs av-faint">
                        {proposal.top_evidence.technologies.join(' · ')}
                      </p>
                    ) : null}
                  </div>
                ) : null}

                <footer className={styles.footer}>
                  <span className="av-small av-faint">Отправлен {timeAgo(proposal.created_at)}</span>
                  <div className="av-row">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={async () => {
                        await post(`/proposals/${proposal.id}/shortlist`, {
                          shortlisted: !proposal.shortlisted_at,
                        });
                        void load(sort);
                      }}
                    >
                      {proposal.shortlisted_at ? 'Убрать из шорт-листа' : 'В шорт-лист'}
                    </Button>
                    <Button size="sm" onClick={() => setHiring(proposal)}>
                      Нанять
                    </Button>
                  </div>
                </footer>
              </Card>
            ))}
          </div>
        )}
      </div>

      <HireSheet
        proposal={hiring}
        project={project}
        onClose={() => setHiring(null)}
        onHired={(contractId) => {
          setHiring(null);
          router.push(`/contracts/${contractId}`);
        }}
      />
    </>
  );
}

function HireSheet({
  proposal,
  project,
  onClose,
  onHired,
}: {
  proposal: ProposalCard | null;
  project: Project | null;
  onClose: () => void;
  onHired: (contractId: string) => void;
}) {
  const [visibility, setVisibility] = useState('range');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  if (!proposal) return null;

  const fee = Math.round(proposal.amount_minor * 0.1);

  return (
    <Sheet
      open={Boolean(proposal)}
      onClose={onClose}
      title={`Нанять: ${proposal.developer.full_name}`}
      description={project?.title}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button
            loading={busy}
            onClick={async () => {
              setBusy(true);
              setMessage('');
              try {
                const contract = await post<{ id: string }>('/contracts', {
                  proposal_id: proposal.id,
                  price_visibility: visibility,
                });
                onHired(contract.id);
              } catch (error) {
                setMessage(
                  error instanceof ApiFailure
                    ? error.message
                    : 'Не удалось создать сделку. Попробуйте ещё раз.',
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            Заключить сделку
          </Button>
        </>
      }
    >
      <div className="av-stack">
        {message ? (
          <p className={styles.alert} role="alert">
            {message}
          </p>
        ) : null}

        <ul className={styles.terms}>
          <li>
            <span className="av-muted">Цена</span>
            <strong>{proposal.amount_display}</strong>
          </li>
          <li>
            <span className="av-muted">Комиссия платформы (удерживается с исполнителя)</span>
            <strong>{money(fee, proposal.currency)}</strong>
          </li>
          <li>
            <span className="av-muted">Срок</span>
            <strong>{days(proposal.delivery_days)}</strong>
          </li>
        </ul>

        <div className="av-stack-sm">
          <p className="av-small av-strong">После завершения показывать стоимость сделки в профиле исполнителя как</p>
          <div className={styles.visibility}>
            {[
              { key: 'public', label: 'Точная сумма' },
              { key: 'range', label: 'Диапазон' },
              { key: 'hidden', label: 'Не показывать' },
              { key: 'private', label: '«Закрытая сделка»' },
            ].map((option) => (
              <button
                key={option.key}
                type="button"
                className={[styles.option, visibility === option.key ? styles.optionActive : ''].join(' ')}
                onClick={() => setVisibility(option.key)}
                aria-pressed={visibility === option.key}
              >
                {visibility === option.key ? <IconCheck size={15} /> : null}
                {option.label}
              </button>
            ))}
          </div>
          <p className="av-small av-faint">
            Это влияет только на публичный профиль исполнителя. Его доходы и баланс не публичны
            в любом случае.
          </p>
        </div>

        <p className={styles.note}>
          <IconShield size={15} />
          Остальные отклики на этот заказ закроются, каждому исполнителю уйдёт причина. Этапы
          оплачиваются по одному — сейчас ничего не списывается.
        </p>
      </div>
    </Sheet>
  );
}
