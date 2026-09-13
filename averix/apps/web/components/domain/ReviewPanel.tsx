'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import styles from './ReviewPanel.module.css';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Field';
import { Avatar } from '@/components/ui/Avatar';
import { IconStar, IconStarFilled } from '@/components/ui/Icon';
import { ApiFailure, get, post } from '@/lib/api';
import { shortDate } from '@/lib/format';
import type { ContractReviews, Review, ReviewCategory } from '@/lib/types';

/**
 * Отзывы по завершённой сделке: своя форма, пока окно открыто, и обе
 * опубликованные стороны после. Отзывы «слепые»: пока второй не написал
 * свой, первый не показывается никому — так никто не подстраивается.
 */
export function ReviewPanel({ contractId }: { contractId: string }) {
  const [panel, setPanel] = useState<ContractReviews | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      setPanel(await get<ContractReviews>(`/contracts/${contractId}/reviews`));
    } catch {
      setFailed(true);
    }
  }, [contractId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (failed) return <p className="av-small av-muted">Не удалось загрузить отзывы.</p>;
  if (!panel) return null;

  const mine = panel.my_direction === 'of_developer' ? panel.of_developer : panel.of_client;
  const aboutMe = panel.my_direction === 'of_developer' ? panel.of_client : panel.of_developer;

  return (
    <div className="av-stack-sm">
      {panel.can_review ? (
        <ReviewForm
          contractId={contractId}
          categories={mine.categories}
          closesAt={panel.window_closes_at}
          onDone={load}
        />
      ) : null}

      {!panel.can_review && panel.my_direction && mine.submitted && !mine.published ? (
        <Card>
          <p className="av-strong">Ваш отзыв отправлен</p>
          <p className="av-small av-muted">
            Он откроется, когда вторая сторона оставит свой отзыв или закончится окно
            {panel.window_closes_at ? ` (${shortDate(panel.window_closes_at)})` : ''}.
          </p>
        </Card>
      ) : null}

      {!panel.can_review && !mine.submitted && panel.reason && panel.my_direction ? (
        <p className="av-small av-muted">{panel.reason}</p>
      ) : null}

      {panel.of_developer.published && panel.of_developer.review ? (
        <ReviewCard review={panel.of_developer.review} heading="Отзыв заказчика об исполнителе" onChanged={load} />
      ) : null}
      {panel.of_client.published && panel.of_client.review ? (
        <ReviewCard review={panel.of_client.review} heading="Отзыв исполнителя о заказчике" onChanged={load} />
      ) : null}

      {aboutMe.submitted && !aboutMe.published ? (
        <p className="av-small av-faint">Вторая сторона уже оставила отзыв — вы увидите его после публикации.</p>
      ) : null}
    </div>
  );
}

function ReviewForm({
  contractId,
  categories,
  closesAt,
  onDone,
}: {
  contractId: string;
  categories: ReviewCategory[];
  closesAt?: string;
  onDone: () => void;
}) {
  const [scores, setScores] = useState<Record<string, number>>({});
  const [comment, setComment] = useState('');
  const [again, setAgain] = useState<boolean | null>(null);
  const [error, setError] = useState('');
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const complete = categories.every((category) => scores[category.key]);

  async function submit() {
    setBusy(true);
    setError('');
    setFields({});
    try {
      await post(`/contracts/${contractId}/reviews`, {
        scores,
        comment: comment.trim(),
        would_work_again: again,
      });
      onDone();
    } catch (failure) {
      if (failure instanceof ApiFailure) {
        setFields(failure.fields);
        setError(Object.keys(failure.fields).length ? '' : failure.message);
      } else {
        setError('Не удалось отправить отзыв.');
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <div className="av-stack">
        <div>
          <p className="av-strong">Оставьте отзыв</p>
          <p className="av-small av-muted">
            Вторая сторона не увидит его, пока не напишет свой
            {closesAt ? `, или до ${shortDate(closesAt)}` : ''}.
          </p>
        </div>
        {error ? (
          <p className={styles.alert} role="alert">
            {error}
          </p>
        ) : null}
        {categories.map((category) => (
          <div key={category.key} className={styles.row}>
            <div>
              <p className="av-small av-strong">{category.label}</p>
              {category.hint ? <p className="av-xs av-faint">{category.hint}</p> : null}
            </div>
            <Stars value={scores[category.key] ?? 0} onChange={(value) => setScores({ ...scores, [category.key]: value })} />
            {fields[`scores.${category.key}`] ? <p className={styles.fieldError}>{fields[`scores.${category.key}`]}</p> : null}
          </div>
        ))}
        <Textarea
          label="Комментарий"
          optional
          placeholder="Что было хорошо, что можно улучшить. Это прочитают другие пользователи."
          max={2000}
          rows={4}
          value={comment}
          error={fields.comment}
          onChange={(event) => setComment(event.target.value)}
        />
        <div className={styles.again}>
          <span className="av-small av-strong">Стали бы работать снова?</span>
          <div className="av-row">
            <Button size="sm" variant={again === true ? 'primary' : 'secondary'} onClick={() => setAgain(true)}>
              Да
            </Button>
            <Button size="sm" variant={again === false ? 'primary' : 'secondary'} onClick={() => setAgain(false)}>
              Нет
            </Button>
          </div>
        </div>
        <Button loading={busy} disabled={!complete} onClick={() => void submit()}>
          Отправить отзыв
        </Button>
      </div>
    </Card>
  );
}

export function Stars({ value, onChange, size = 22 }: { value: number; onChange?: (value: number) => void; size?: number }) {
  return (
    <div className={styles.stars} role={onChange ? 'radiogroup' : undefined} aria-label="Оценка">
      {[1, 2, 3, 4, 5].map((star) =>
        onChange ? (
          <button
            key={star}
            type="button"
            role="radio"
            aria-checked={value === star}
            aria-label={`${star} из 5`}
            className={[styles.star, star <= value ? styles.starOn : ''].join(' ')}
            onClick={() => onChange(star)}
          >
            {star <= value ? <IconStarFilled size={size} /> : <IconStar size={size} />}
          </button>
        ) : (
          <span key={star} className={[styles.star, star <= Math.round(value) ? styles.starOn : ''].join(' ')}>
            {star <= Math.round(value) ? <IconStarFilled size={size} /> : <IconStar size={size} />}
          </span>
        ),
      )}
    </div>
  );
}

export function ReviewCard({ review, heading, onChanged }: { review: Review; heading?: string; onChanged?: () => void }) {
  const [reply, setReply] = useState('');
  const [replying, setReplying] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  return (
    <Card>
      <div className="av-stack-sm">
        {heading ? <p className="av-xs av-faint">{heading}</p> : null}
        <div className={styles.head}>
          <Link href={`/developers/${review.author.username}`} className={styles.author}>
            <Avatar src={review.author.photo_url} name={review.author.full_name} size={40} />
            <div>
              <p className="av-small av-strong">{review.author.full_name}</p>
              <p className="av-xs av-faint">
                {review.contract_title ? `${review.contract_title} · ` : ''}
                {shortDate(review.published_at ?? review.created_at)}
              </p>
            </div>
          </Link>
          <div className={styles.overall}>
            <Stars value={review.overall} size={14} />
            <span className="av-small av-numeric">{review.overall.toFixed(1)}</span>
          </div>
        </div>
        {review.comment ? <p className={styles.comment}>{review.comment}</p> : null}
        {review.would_work_again !== undefined && review.would_work_again !== null ? (
          <p className="av-xs av-muted">
            {review.would_work_again ? 'Готов работать снова' : 'Не стал бы работать снова'}
          </p>
        ) : null}
        {review.response ? (
          <blockquote className={styles.response}>
            <span className="av-xs av-faint">Ответ {review.subject.full_name}</span>
            {review.response}
          </blockquote>
        ) : review.can_respond ? (
          replying ? (
            <div className="av-stack-sm">
              <Textarea
                label="Ваш ответ"
                max={1000}
                rows={3}
                value={reply}
                error={error || undefined}
                onChange={(event) => setReply(event.target.value)}
              />
              <div className="av-row">
                <Button
                  size="sm"
                  loading={busy}
                  disabled={reply.trim().length < 3}
                  onClick={async () => {
                    setBusy(true);
                    setError('');
                    try {
                      await post(`/reviews/${review.id}/response`, { response: reply.trim() });
                      setReplying(false);
                      onChanged?.();
                    } catch (failure) {
                      setError(failure instanceof ApiFailure ? failure.fields.response || failure.message : 'Не удалось отправить.');
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  Опубликовать ответ
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setReplying(false)}>
                  Отмена
                </Button>
              </div>
            </div>
          ) : (
            <Button size="sm" variant="secondary" onClick={() => setReplying(true)}>
              Ответить публично
            </Button>
          )
        ) : null}
      </div>
    </Card>
  );
}
