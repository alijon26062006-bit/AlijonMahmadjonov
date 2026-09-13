'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import styles from './onboarding.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Avatar } from '@/components/ui/Avatar';
import { ChoiceChip, Input, Select, Textarea } from '@/components/ui/Field';
import { Skeleton } from '@/components/ui/Skeleton';
import { IconCheck, IconClose } from '@/components/ui/Icon';
import { ApiFailure, get, post, put, upload } from '@/lib/api';
import { avatarURL } from '@/lib/photo';
import { AVAILABILITY, CURRENCIES, EXPERIENCE, PROFICIENCY, SKILL_LEVEL } from '@/lib/labels';
import { useSession } from '@/lib/session';
import type { OwnProfile, Skill, Specialisation, StepResult } from '@/lib/types';

const TOTAL = 9;

type Draft = {
  full_name: string;
  country_code: string;
  city: string;
  timezone: string;
  languages: { language: string; proficiency: string }[];
  specialisation: string;
  professional_title: string;
  additional: string[];
  technologies: { slug: string; name: string; level: string; years?: number }[];
  experience_level: string;
  years_experience: string;
  hourly_rate: string;
  min_project: string;
  currency: string;
  availability: string;
  hours_per_week: string;
  open_to_invitations: boolean;
  show_location: boolean;
  show_hourly_rate: boolean;
  bio: string;
};

const EMPTY: Draft = {
  full_name: '',
  country_code: '',
  city: '',
  timezone: '',
  languages: [{ language: 'Русский', proficiency: 'native' }],
  specialisation: '',
  professional_title: '',
  additional: [],
  technologies: [],
  experience_level: 'mid',
  years_experience: '',
  hourly_rate: '',
  min_project: '',
  currency: 'RUB',
  availability: 'available',
  hours_per_week: '',
  open_to_invitations: true,
  show_location: true,
  show_hourly_rate: true,
  bio: '',
};

/**
 * Анкета исполнителя.
 *
 * Девять шагов, каждый сохраняется на сервере сразу: человек может закрыть
 * вкладку на шестом шаге и вернуться туда же. Ничего не собирается «в конце»
 * — иначе потеря соединения стоила бы всей работы.
 */
export default function OnboardingPage() {
  const router = useRouter();
  const { session, refresh } = useSession();
  const [profile, setProfile] = useState<OwnProfile | null>(null);
  const [step, setStep] = useState(1);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [specialisations, setSpecialisations] = useState<Specialisation[]>([]);
  const [suggested, setSuggested] = useState<Skill[]>([]);
  const [skillQuery, setSkillQuery] = useState('');
  const [found, setFound] = useState<Skill[]>([]);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [resending, setResending] = useState(false);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    get<OwnProfile>('/developers/me')
      .then((data) => {
        setProfile(data);
        setDraft((current) => ({
          ...current,
          full_name: data.full_name || current.full_name,
          country_code: data.country_code ?? '',
          city: data.city ?? '',
          timezone: data.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone,
          languages: data.languages?.length ? data.languages : current.languages,
          specialisation: data.primary_specialisation?.slug ?? '',
          professional_title: data.professional_title ?? '',
          additional: (data.additional_specialisations ?? []).map((item) => item.slug),
          technologies: (data.skills ?? []).map((skill) => ({
            slug: skill.slug,
            name: skill.name,
            level: skill.level ?? 'working',
            years: skill.years,
          })),
          experience_level: data.experience_level || current.experience_level,
          years_experience: data.years_experience ? String(data.years_experience) : '',
          hourly_rate: data.hourly_rate_minor ? String(Math.round(data.hourly_rate_minor / 100)) : '',
          min_project: data.min_project_minor ? String(Math.round(data.min_project_minor / 100)) : '',
          currency: data.rate_currency || current.currency,
          availability: data.availability || current.availability,
          hours_per_week: data.hours_per_week ? String(data.hours_per_week) : '',
          open_to_invitations: data.open_to_invitations ?? true,
          show_location: data.show_location ?? true,
          show_hourly_rate: data.show_hourly_rate ?? true,
          bio: data.bio ?? '',
        }));
        const next = data.onboarding?.completed ? 1 : Math.min(Math.max(data.onboarding?.step || 1, 1), TOTAL);
        setStep(next);
      })
      .catch(() => setMessage('Не удалось загрузить анкету. Обновите страницу.'));

    get<Specialisation[]>('/taxonomy/specialisations')
      .then(setSpecialisations)
      .catch(() => undefined);
  }, []);

  // Навыки, которые обычно нужны в выбранной профессии.
  useEffect(() => {
    if (!draft.specialisation) return;
    get<Skill[]>(`/taxonomy/specialisations/${draft.specialisation}/skills`)
      .then(setSuggested)
      .catch(() => setSuggested([]));
  }, [draft.specialisation]);

  useEffect(() => {
    const query = skillQuery.trim();
    if (query.length < 2) {
      setFound([]);
      return;
    }
    const timer = setTimeout(() => {
      get<Skill[]>(`/taxonomy/skills?q=${encodeURIComponent(query)}`)
        .then(setFound)
        .catch(() => setFound([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [skillQuery]);

  const set = useCallback(<K extends keyof Draft>(key: K, value: Draft[K]) => {
    setDraft((current) => ({ ...current, [key]: value }));
  }, []);

  function toggleSkill(skill: { slug: string; name: string }) {
    setDraft((current) => {
      const has = current.technologies.some((item) => item.slug === skill.slug);
      return {
        ...current,
        technologies: has
          ? current.technologies.filter((item) => item.slug !== skill.slug)
          : [...current.technologies, { slug: skill.slug, name: skill.name, level: 'working' }],
      };
    });
  }

  async function save() {
    setBusy(true);
    setFields({});
    setMessage('');
    try {
      const result = await submitStep(step, draft);
      if (result?.profile) setProfile(result.profile);
      else if (step === 8) setProfile(await get<OwnProfile>('/developers/me'));
      if (step === TOTAL) {
        await refresh();
        router.replace(`/developers/${session?.username ?? ''}`);
        return;
      }
      setStep(step + 1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (error) {
      if (error instanceof ApiFailure) {
        setFields(error.fields);
        setMessage(Object.keys(error.fields).length ? 'Проверьте отмеченные поля.' : error.message);
      } else {
        setMessage('Не удалось сохранить. Проверьте подключение.');
      }
    } finally {
      setBusy(false);
    }
  }

  const canContinue = useMemo(() => validate(step, draft), [step, draft]);

  if (!profile) {
    return (
      <>
        <TopBar title="Анкета исполнителя" />
        <div className="av-page av-stack">
          <Skeleton height={40} />
          <Skeleton height={200} />
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar title="Анкета исполнителя" />
      <div className={`av-page ${styles.shell}`}>
        <div className={styles.progress}>
          <div className={styles.track} aria-hidden="true">
            <span className={styles.fill} style={{ width: `${(step / TOTAL) * 100}%` }} />
          </div>
          <span className={styles.stepLabel}>
            Шаг {step} из {TOTAL}
          </span>
        </div>

        <Card>
          <div className="av-stack">
            <div>
              <h1 className={styles.title}>{STEPS[step - 1].title}</h1>
              <p className={styles.lede}>{STEPS[step - 1].lede}</p>
            </div>

            {message ? (
              <p className={styles.alert} role="alert">
                {message}
              </p>
            ) : null}

            {step === 1 ? (
              <div className="av-stack">
                <Input
                  label="Имя и фамилия"
                  value={draft.full_name}
                  error={fields.full_name}
                  onChange={(event) => set('full_name', event.target.value)}
                />
                <div className="av-row">
                  <Input
                    label="Код страны"
                    placeholder="RU"
                    maxLength={2}
                    value={draft.country_code}
                    error={fields.country_code}
                    onChange={(event) => set('country_code', event.target.value.toUpperCase())}
                  />
                  <Input
                    label="Город"
                    optional
                    value={draft.city}
                    error={fields.city}
                    onChange={(event) => set('city', event.target.value)}
                  />
                </div>
                <Input
                  label="Часовой пояс"
                  hint="Например, Europe/Moscow или Asia/Tashkent."
                  value={draft.timezone}
                  error={fields.timezone}
                  onChange={(event) => set('timezone', event.target.value)}
                />
                <div className="av-stack-sm">
                  <p className="av-small av-strong">Языки</p>
                  {draft.languages.map((language, index) => (
                    <div key={index} className={styles.languageRow}>
                      <Input
                        label="Язык"
                        value={language.language}
                        onChange={(event) => {
                          const next = [...draft.languages];
                          next[index] = { ...next[index], language: event.target.value };
                          set('languages', next);
                        }}
                      />
                      <Select
                        label="Уровень"
                        value={language.proficiency}
                        onChange={(event) => {
                          const next = [...draft.languages];
                          next[index] = { ...next[index], proficiency: event.target.value };
                          set('languages', next);
                        }}
                      >
                        {Object.entries(PROFICIENCY).map(([key, label]) => (
                          <option key={key} value={key}>
                            {label}
                          </option>
                        ))}
                      </Select>
                      {draft.languages.length > 1 ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label="Убрать язык"
                          icon={<IconClose size={16} />}
                          onClick={() => set('languages', draft.languages.filter((_, i) => i !== index))}
                        />
                      ) : (
                        <span />
                      )}
                    </div>
                  ))}
                  {draft.languages.length < 5 ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => set('languages', [...draft.languages, { language: '', proficiency: 'conversational' }])}
                    >
                      Добавить язык
                    </Button>
                  ) : null}
                </div>
              </div>
            ) : null}

            {step === 2 ? (
              <div className="av-stack">
                <div className={styles.sectorGrid}>
                  {specialisations.map((specialisation) => (
                    <button
                      key={specialisation.slug}
                      type="button"
                      className={[
                        styles.sector,
                        draft.specialisation === specialisation.slug ? styles.sectorActive : '',
                      ].join(' ')}
                      onClick={() => set('specialisation', specialisation.slug)}
                      aria-pressed={draft.specialisation === specialisation.slug}
                    >
                      <span className={styles.sectorName}>{specialisation.name}</span>
                      {specialisation.description ? (
                        <span className={styles.sectorHint}>{specialisation.description}</span>
                      ) : null}
                    </button>
                  ))}
                </div>
                {fields.slug ? <p className={styles.alert}>{fields.slug}</p> : null}
                <Input
                  label="Как вас представить"
                  optional
                  placeholder="Например: Дизайнер логотипов и фирменного стиля"
                  hint="Эта строка стоит под вашим именем в поиске."
                  value={draft.professional_title}
                  error={fields.professional_title}
                  onChange={(event) => set('professional_title', event.target.value)}
                />
              </div>
            ) : null}

            {step === 3 ? (
              <div className="av-stack">
                <div className={styles.chips}>
                  {specialisations
                    .filter((specialisation) => specialisation.slug !== draft.specialisation)
                    .map((specialisation) => (
                      <ChoiceChip
                        key={specialisation.slug}
                        selected={draft.additional.includes(specialisation.slug)}
                        disabled={!draft.additional.includes(specialisation.slug) && draft.additional.length >= 3}
                        onToggle={() =>
                          set(
                            'additional',
                            draft.additional.includes(specialisation.slug)
                              ? draft.additional.filter((slug) => slug !== specialisation.slug)
                              : [...draft.additional, specialisation.slug],
                          )
                        }
                      >
                        {specialisation.name}
                      </ChoiceChip>
                    ))}
                </div>
                {fields.slugs ? <p className={styles.alert}>{fields.slugs}</p> : null}
                <p className="av-small av-faint">Не больше трёх. Можно пропустить.</p>
              </div>
            ) : null}

            {step === 4 ? (
              <div className="av-stack">
                <Input
                  label="Найти навык"
                  placeholder="Figma, Photoshop, копирайтинг, Python…"
                  value={skillQuery}
                  onChange={(event) => setSkillQuery(event.target.value)}
                />
                {found.length ? (
                  <div className={styles.chips}>
                    {found.map((skill) => (
                      <ChoiceChip
                        key={skill.slug}
                        selected={draft.technologies.some((item) => item.slug === skill.slug)}
                        onToggle={() => toggleSkill(skill)}
                      >
                        {skill.name}
                      </ChoiceChip>
                    ))}
                  </div>
                ) : null}

                {suggested.length ? (
                  <div className="av-stack-sm">
                    <p className="av-small av-strong">Обычно нужны в вашей профессии</p>
                    <div className={styles.chips}>
                      {suggested.map((skill) => (
                        <ChoiceChip
                          key={skill.slug}
                          selected={draft.technologies.some((item) => item.slug === skill.slug)}
                          onToggle={() => toggleSkill(skill)}
                        >
                          {skill.name}
                        </ChoiceChip>
                      ))}
                    </div>
                  </div>
                ) : null}

                {draft.technologies.length ? (
                  <div className="av-stack-sm">
                    <p className="av-small av-strong">Ваш уровень</p>
                    {draft.technologies.map((technology) => (
                      <div key={technology.slug} className={styles.skillRow}>
                        <span className="av-small av-strong">{technology.name}</span>
                        <div className={styles.levels}>
                          {Object.entries(SKILL_LEVEL).map(([key, label]) => (
                            <button
                              key={key}
                              type="button"
                              className={[styles.level, technology.level === key ? styles.levelActive : ''].join(' ')}
                              onClick={() =>
                                set(
                                  'technologies',
                                  draft.technologies.map((item) =>
                                    item.slug === technology.slug ? { ...item, level: key } : item,
                                  ),
                                )
                              }
                              aria-pressed={technology.level === key}
                            >
                              {label}
                            </button>
                          ))}
                          <button
                            type="button"
                            className={styles.level}
                            aria-label={`Убрать ${technology.name}`}
                            onClick={() => toggleSkill(technology)}
                          >
                            <IconClose size={13} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
                {fields.technologies || fields.slugs ? (
                  <p className={styles.alert}>{fields.technologies ?? fields.slugs}</p>
                ) : null}
              </div>
            ) : null}

            {step === 5 ? (
              <div className="av-stack">
                <Select
                  label="Уровень опыта"
                  value={draft.experience_level}
                  error={fields.experience_level}
                  onChange={(event) => set('experience_level', event.target.value)}
                >
                  {['junior', 'mid', 'senior', 'lead'].map((level) => (
                    <option key={level} value={level}>
                      {EXPERIENCE[level]}
                    </option>
                  ))}
                </Select>
                <Input
                  label="Лет опыта"
                  inputMode="numeric"
                  optional
                  value={draft.years_experience}
                  error={fields.years_experience}
                  onChange={(event) => set('years_experience', event.target.value)}
                />
                <Select label="Валюта" value={draft.currency} onChange={(event) => set('currency', event.target.value)}>
                  {CURRENCIES.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </Select>
                <Input
                  label="Ставка за час"
                  optional
                  inputMode="numeric"
                  hint="Ориентир для заказчика. Можно скрыть на следующем шаге."
                  value={draft.hourly_rate}
                  error={fields.hourly_rate_minor}
                  onChange={(event) => set('hourly_rate', event.target.value)}
                />
                <Input
                  label="Минимальный заказ"
                  optional
                  inputMode="numeric"
                  value={draft.min_project}
                  error={fields.min_project_minor}
                  onChange={(event) => set('min_project', event.target.value)}
                />
              </div>
            ) : null}

            {step === 6 ? (
              <div className="av-stack">
                <Select
                  label="Занятость"
                  value={draft.availability}
                  error={fields.availability}
                  onChange={(event) => set('availability', event.target.value)}
                >
                  {Object.entries(AVAILABILITY).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </Select>
                <Input
                  label="Часов в неделю"
                  optional
                  inputMode="numeric"
                  value={draft.hours_per_week}
                  error={fields.hours_per_week}
                  onChange={(event) => set('hours_per_week', event.target.value)}
                />
                <Toggle
                  label="Получать приглашения на заказы"
                  hint="Заказчики смогут приглашать вас лично."
                  checked={draft.open_to_invitations}
                  onChange={(value) => set('open_to_invitations', value)}
                />
                <Toggle
                  label="Показывать город в профиле"
                  checked={draft.show_location}
                  onChange={(value) => set('show_location', value)}
                />
                <Toggle
                  label="Показывать ставку в профиле"
                  checked={draft.show_hourly_rate}
                  onChange={(value) => set('show_hourly_rate', value)}
                />
              </div>
            ) : null}

            {step === 7 ? (
              <Textarea
                label="О себе"
                placeholder="Чем вы занимаетесь, для кого и что получает заказчик. Конкретика работает лучше эпитетов."
                hint="Не меньше 120 символов."
                max={3000}
                rows={9}
                value={draft.bio}
                error={fields.bio}
                onChange={(event) => set('bio', event.target.value)}
              />
            ) : null}

            {step === 8 ? (
              <PhotoStep profile={profile} onUploaded={(next) => setProfile(next)} />
            ) : null}

            {step === 9 ? (
              <div className="av-stack">
                <ul className={styles.missing}>
                  {(profile.onboarding?.missing ?? []).length === 0 ? (
                    <li>
                      <IconCheck size={15} /> Всё заполнено.
                    </li>
                  ) : (
                    profile.onboarding.missing!.map((item) => (
                      <li key={item.key}>
                        <IconClose size={15} /> {item.label}
                      </li>
                    ))
                  )}
                </ul>

                {/* Публикация требует подтверждённой почты, поэтому об этом
                    говорится до нажатия кнопки, а не после отказа. */}
                {profile.email_verified ? null : (
                  <div className={styles.notice}>
                    <p className="av-small av-strong">Подтвердите адрес почты</p>
                    <p className="av-small">
                      Мы отправили письмо со ссылкой при регистрации. Пока адрес не подтверждён,
                      анкету нельзя опубликовать — так на площадке не заводятся анкеты на чужие
                      адреса.
                    </p>
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={resending}
                      onClick={async () => {
                        setResending(true);
                        setMessage('');
                        try {
                          await post('/auth/email/resend');
                          setSent(true);
                        } catch (error) {
                          setMessage(error instanceof ApiFailure ? error.message : 'Письмо отправить не удалось.');
                        } finally {
                          setResending(false);
                        }
                      }}
                    >
                      Отправить письмо ещё раз
                    </Button>
                    {sent ? <p className="av-small av-muted">Письмо отправлено — проверьте почту.</p> : null}
                  </div>
                )}

                {/* Отказ на последнем шаге приходит по полям, а полей тут нет:
                    без этого списка кнопка просто ничего бы не делала. */}
                {Object.keys(fields).length > 0 ? (
                  <ul className={styles.missing}>
                    {Object.entries(fields).map(([key, text]) => (
                      <li key={key} style={{ color: 'var(--av-danger-text)' }}>
                        <IconClose size={15} /> {text}
                      </li>
                    ))}
                  </ul>
                ) : null}

                <p className="av-small av-muted">
                  После публикации анкета появится в каталоге исполнителей, и подходящие заказы начнут
                  приходить в ленту. Изменить всё это можно в любой момент.
                </p>
              </div>
            ) : null}

            <div className={styles.actions}>
              {step > 1 ? (
                <Button variant="secondary" onClick={() => setStep(step - 1)}>
                  Назад
                </Button>
              ) : null}
              {OPTIONAL_STEPS.includes(step) && step < TOTAL ? (
                <Button variant="ghost" onClick={() => setStep(step + 1)}>
                  Пропустить
                </Button>
              ) : null}
              <Button loading={busy} disabled={!canContinue} onClick={() => void save()}>
                {step === TOTAL ? 'Опубликовать анкету' : 'Далее'}
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </>
  );
}

const OPTIONAL_STEPS = [3, 8];

const STEPS = [
  { title: 'Кто вы и где', lede: 'Имя видят заказчики. Часовой пояс нужен, чтобы понимать, когда вы на связи.' },
  { title: 'Чем вы занимаетесь', lede: 'Главная профессия определяет, какие заказы вам будут приходить.' },
  { title: 'Дополнительные направления', lede: 'Если вы работаете ещё в чём-то — отметьте. Не больше трёх.' },
  { title: 'Навыки и инструменты', lede: 'По ним заказ находит вас. Отмечайте только то, чем действительно владеете.' },
  { title: 'Опыт и цены', lede: 'Ставку можно скрыть от чужих глаз на следующем шаге.' },
  { title: 'Занятость и приватность', lede: 'Что показывать в профиле и готовы ли вы к приглашениям.' },
  { title: 'О себе', lede: 'Это первое, что читает заказчик после имени.' },
  { title: 'Фотография', lede: 'С лицом откликам доверяют заметно больше. Шаг можно пропустить.' },
  { title: 'Готово', lede: 'Проверьте, что ничего важного не осталось пустым.' },
];

function validate(step: number, draft: Draft): boolean {
  switch (step) {
    case 1:
      return draft.full_name.trim().length >= 2 && draft.timezone.trim().length > 0;
    case 2:
      return Boolean(draft.specialisation);
    case 3:
      return true;
    case 4:
      return draft.technologies.length > 0;
    case 5:
      return Boolean(draft.experience_level);
    case 6:
      return Boolean(draft.availability);
    case 7:
      return draft.bio.trim().length >= 120;
    case 8:
      return true;
    default:
      return true;
  }
}

async function submitStep(step: number, draft: Draft): Promise<StepResult | null> {
  const minor = (value: string) => {
    const number = Number(value.replace(/[^\d.]/g, ''));
    return Number.isFinite(number) && number > 0 ? Math.round(number * 100) : null;
  };

  switch (step) {
    case 1:
      return put<StepResult>('/developers/me/basics', {
        full_name: draft.full_name.trim(),
        country_code: draft.country_code.trim(),
        city: draft.city.trim(),
        timezone: draft.timezone.trim(),
        languages: draft.languages.filter((language) => language.language.trim()),
      });
    case 2:
      return put<StepResult>('/developers/me/specialisation', {
        slug: draft.specialisation,
        professional_title: draft.professional_title.trim(),
      });
    case 3:
      return put<StepResult>('/developers/me/additional-specialisations', { slugs: draft.additional });
    case 4:
      return put<StepResult>('/developers/me/technologies', {
        technologies: draft.technologies.map((technology) => ({
          slug: technology.slug,
          level: technology.level,
          years: technology.years,
        })),
      });
    case 5:
      return put<StepResult>('/developers/me/experience', {
        experience_level: draft.experience_level,
        years_experience: draft.years_experience ? Number(draft.years_experience) : null,
        hourly_rate_minor: minor(draft.hourly_rate),
        min_project_minor: minor(draft.min_project),
        currency: draft.currency,
      });
    case 6:
      return put<StepResult>('/developers/me/availability', {
        availability: draft.availability,
        hours_per_week: draft.hours_per_week ? Number(draft.hours_per_week) : null,
        open_to_invitations: draft.open_to_invitations,
        show_location: draft.show_location,
        show_hourly_rate: draft.show_hourly_rate,
      });
    case 7:
      return put<StepResult>('/developers/me/bio', {
        bio: draft.bio.trim(),
        professional_title: draft.professional_title.trim(),
      });
    case 8:
      return null;
    default:
      return post<StepResult>('/developers/me/finish');
  }
}

function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="av-row-between" style={{ gap: 'var(--av-space-4)', cursor: 'pointer' }}>
      <span>
        <span className="av-small av-strong">{label}</span>
        {hint ? <span className="av-xs av-faint" style={{ display: 'block' }}>{hint}</span> : null}
      </span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    </label>
  );
}

function PhotoStep({ profile, onUploaded }: { profile: OwnProfile; onUploaded: (profile: OwnProfile) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const picker = useRef<HTMLInputElement>(null);

  async function choose(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError('');
    try {
      const form = new FormData();
      form.append('photo', file);
      await upload('/developers/me/photo', form);
      onUploaded(await get<OwnProfile>('/developers/me'));
    } catch (failure) {
      setError(failure instanceof ApiFailure ? failure.message : 'Не удалось загрузить фотографию.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="av-stack">
      <div className={styles.photoRow}>
        <Avatar src={avatarURL(profile.photo, 128)} name={profile.full_name} size={96} />
        <div className="av-stack-sm">
          <input
            ref={picker}
            type="file"
            accept="image/*"
            hidden
            onChange={(event) => void choose(event)}
          />
          <Button variant="secondary" loading={busy} onClick={() => picker.current?.click()}>
            {profile.photo ? 'Заменить фотографию' : 'Загрузить фотографию'}
          </Button>
          <p className="av-xs av-faint">JPEG или PNG, квадратная лучше всего.</p>
        </div>
      </div>
      {error ? <p className={styles.alert}>{error}</p> : null}
    </div>
  );
}
