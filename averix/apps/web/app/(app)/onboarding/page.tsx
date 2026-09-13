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
import type { Category, OwnProfile, PortfolioCard, Skill, Specialisation, StepResult } from '@/lib/types';

/**
 * Анкета — это четыре экрана, а не девять.
 *
 * Разделов внутри по-прежнему девять: каждый сохраняется своим запросом, и
 * это правильно — так «Назад» ничего не теряет, а закрытая вкладка не
 * обнуляет работу. Но человеку показываются три коротких шага и сводка.
 * Девять экранов подряд бросают на пятом.
 */
const STAGES = [
  {
    title: 'О себе',
    lede: 'Имя, город и профессия — то, что заказчик видит первым.',
    sections: [1, 2, 3, 8],
  },
  {
    title: 'Что вы умеете',
    lede: 'Навыки, опыт, занятость и несколько слов о себе.',
    sections: [4, 5, 6, 7],
  },
  {
    title: 'Ваши работы',
    lede: 'Хотя бы одна — без неё заявку отправить нельзя.',
    sections: [] as number[],
  },
  {
    title: 'Проверьте и отправьте',
    lede: 'Всё ли верно? Заявку посмотрит администратор.',
    sections: [] as number[],
  },
];

const TOTAL = STAGES.length;
const PORTFOLIO_STAGE = 3;
const REVIEW_STAGE = 4;

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
  const [stage, setStage] = useState(1);

  // Сначала вспомнить, где человек был, и только потом начать запоминать:
  // иначе первый же проход эффекта записал бы единицу поверх четвёрки, и
  // перезагрузка на последнем шаге отбрасывала бы в начало.
  const restored = useRef(false);
  useEffect(() => {
    try {
      const saved = Number(sessionStorage.getItem(STAGE_KEY) || 0);
      if (saved >= 1 && saved <= TOTAL) setStage(saved);
    } catch {
      // Приватный режим: откроем с начала, это не повод ломать форму.
    }
    restored.current = true;
  }, []);

  useEffect(() => {
    if (!restored.current) return;
    try {
      sessionStorage.setItem(STAGE_KEY, String(stage));
    } catch {
      // Там же.
    }
  }, [stage]);

  // Разделы этого экрана: внутри их несколько, снаружи это один шаг.
  const sections = STAGES[stage - 1].sections;
  const has = (section: number) => sections.includes(section);
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
        // Отправленную анкету открываем на её статусе; в остальном не тянем
        // человека назад — он мог вернуться сюда сам, чтобы что-то поправить.
        setStage((current) =>
          data.onboarding?.completed ? REVIEW_STAGE : Math.max(current, openingStage(data)),
        );
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

  // Сохранение — по разделам, по одному запросу на раздел. Так «Назад»
  // возвращает к уже сохранённому, а не к пустой форме.
  async function save() {
    setBusy(true);
    setFields({});
    setMessage('');
    try {
      for (const section of sections) {
        const result = await submitStep(section, draft);
        if (result?.profile) setProfile(result.profile);
      }
      if (sections.includes(8)) setProfile(await get<OwnProfile>('/developers/me'));
      setStage(stage + 1);
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

  // Последний экран: заявка уходит человеку, который её посмотрит.
  async function submitApplication() {
    setBusy(true);
    setFields({});
    setMessage('');
    try {
      const updated = await post<OwnProfile>('/developers/me/finish');
      setProfile(updated);
      await refresh();
    } catch (error) {
      if (error instanceof ApiFailure) {
        setFields(error.fields);
        setMessage(
          Object.keys(error.fields).length
            ? 'Заявку пока отправить нельзя — посмотрите, чего не хватает.'
            : error.message,
        );
      } else {
        setMessage('Не удалось отправить. Проверьте подключение.');
      }
    } finally {
      setBusy(false);
    }
  }

  const canContinue = useMemo(() => sections.every((section) => validate(section, draft)), [sections, draft]);

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
            <span className={styles.fill} style={{ width: `${(stage / TOTAL) * 100}%` }} />
          </div>
          <ol className={styles.dots}>
            {STAGES.map((item, index) => (
              <li
                key={item.title}
                className={[
                  styles.dot,
                  index + 1 === stage ? styles.dotNow : '',
                  index + 1 < stage ? styles.dotDone : '',
                ].join(' ')}
                aria-current={index + 1 === stage ? 'step' : undefined}
              >
                <span className={styles.dotMark} aria-hidden="true">
                  {index + 1 < stage ? <IconCheck size={13} /> : index + 1}
                </span>
                <span className={styles.dotLabel}>{item.title}</span>
              </li>
            ))}
          </ol>
          <span className={styles.stepLabel}>
            Шаг {stage} из {TOTAL}
          </span>
        </div>

        <Card>
          <div className="av-stack">
            <div>
              <h1 className={styles.title}>{STAGES[stage - 1].title}</h1>
              <p className={styles.lede}>{STAGES[stage - 1].lede}</p>
            </div>

            {message ? (
              <p className={styles.alert} role="alert">
                {message}
              </p>
            ) : null}

            {has(1) ? (
              <div className="av-stack">
                <h2 className={styles.sectionTitle}>{SECTION_TITLES[1]}</h2>
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

            {has(2) ? (
              <div className="av-stack">
                <h2 className={styles.sectionTitle}>{SECTION_TITLES[2]}</h2>
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

            {has(3) ? (
              <div className="av-stack">
                <h2 className={styles.sectionTitle}>{SECTION_TITLES[3]}</h2>
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

            {has(4) ? (
              <div className="av-stack">
                <h2 className={styles.sectionTitle}>{SECTION_TITLES[4]}</h2>
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

            {has(5) ? (
              <div className="av-stack">
                <h2 className={styles.sectionTitle}>{SECTION_TITLES[5]}</h2>
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

            {has(6) ? (
              <div className="av-stack">
                <h2 className={styles.sectionTitle}>{SECTION_TITLES[6]}</h2>
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

            {has(7) ? (
              <div className="av-stack">
                <h2 className={styles.sectionTitle}>{SECTION_TITLES[7]}</h2>
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
              </div>
            ) : null}

            {has(8) ? (
              <div className="av-stack">
                <h2 className={styles.sectionTitle}>{SECTION_TITLES[8]}</h2>
                <PhotoStep profile={profile} onUploaded={(next) => setProfile(next)} />
              </div>
            ) : null}

            {/* Шаг 3: работы. Без единой отправить заявку нельзя, и лучше
                сказать это здесь, чем на кнопке в самом конце. */}
            {stage === PORTFOLIO_STAGE ? (
              <PortfolioStage
                profile={profile}
                onAdded={async () => setProfile(await get<OwnProfile>('/developers/me'))}
              />
            ) : null}

            {/* Шаг 4: сводка и отправка. */}
            {stage === REVIEW_STAGE ? (
              <div className="av-stack">
                {profile.onboarding?.status === 'review' ? (
                  <div className={styles.notice}>
                    <p className="av-small av-strong">Заявка на рассмотрении</p>
                    <p className="av-small">
                      Мы получили анкету и работы. Их смотрит администратор — обычно это занимает день.
                      Как только будет решение, придёт уведомление, и профиль появится в каталоге.
                      {profile.identity_verified
                        ? ''
                        : ' Пока ждёте, пройдите проверку личности — без неё нельзя откликаться на заказы.'}
                    </p>
                    <div className="av-row av-wrap" style={{ marginTop: 'var(--av-space-3)' }}>
                      {profile.identity_verified ? (
                        <Button variant="secondary" size="sm" onClick={() => router.replace(`/developers/${session?.username ?? ''}`)}>
                          Посмотреть анкету
                        </Button>
                      ) : (
                        <Button size="sm" onClick={() => router.replace('/settings/verification')}>
                          Пройти проверку личности
                        </Button>
                      )}
                    </div>
                  </div>
                ) : (
                  <>
                    <Summary profile={profile} draft={draft} />

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

                    {/* Отправка требует подтверждённой почты, поэтому об этом
                        говорится до нажатия кнопки, а не после отказа. */}
                    {profile.email_verified ? null : (
                      <div className={styles.notice}>
                        <p className="av-small av-strong">Подтвердите адрес почты</p>
                        <p className="av-small">
                          Мы отправили письмо со ссылкой при регистрации. Пока адрес не подтверждён,
                          заявку отправить нельзя — так на площадке не заводятся анкеты на чужие
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

                    {/* Отказ приходит по полям, а полей на этом экране нет:
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
                      Заявку посмотрит администратор. После одобрения анкета появится в каталоге, и
                      подходящие заказы начнут приходить в ленту. Менять её можно и потом.
                    </p>
                  </>
                )}
              </div>
            ) : null}

            {/* Уже отправлено — менять экран кнопками не нужно. */}
            {profile.onboarding?.status === 'review' ? null : (
              <div className={styles.actions}>
                {stage > 1 ? (
                  <Button variant="secondary" onClick={() => setStage(stage - 1)}>
                    Назад
                  </Button>
                ) : null}

                {stage === REVIEW_STAGE ? (
                  <Button
                    loading={busy}
                    disabled={!profile.email_verified || (profile.onboarding?.work_samples ?? 0) === 0}
                    onClick={() => void submitApplication()}
                  >
                    Отправить заявку
                  </Button>
                ) : stage === PORTFOLIO_STAGE ? (
                  <Button
                    disabled={(profile.onboarding?.work_samples ?? 0) === 0}
                    onClick={() => setStage(stage + 1)}
                  >
                    Далее
                  </Button>
                ) : (
                  <Button loading={busy} disabled={!canContinue} onClick={() => void save()}>
                    Далее
                  </Button>
                )}
              </div>
            )}
          </div>
        </Card>
      </div>
    </>
  );
}

/** Где человек остановился в этой вкладке. Переживает перезагрузку. */
const STAGE_KEY = 'averix.onboarding.stage';

/**
 * С какого экрана открыть анкету у того, кто вернулся.
 *
 * Не по счётчику шагов: разделы сохраняются по одному, и счётчик после
 * фотографии показывал бы на первый экран. Смотрим на то, что заполнено.
 */
function openingStage(profile: OwnProfile): number {
  if (profile.onboarding?.completed) return REVIEW_STAGE;
  const named = Boolean(profile.primary_specialisation) && Boolean(profile.full_name);
  const described =
    (profile.skills?.length ?? 0) > 0 &&
    (profile.bio ?? '').trim().length >= 120 &&
    Boolean(profile.experience_level);
  if (!named) return 1;
  if (!described) return 2;
  return PORTFOLIO_STAGE;
}

// Подписи разделов внутри шага: по ним человек понимает, что именно от него
// просят в этом блоке. Заголовок экрана при этом остаётся один.
const SECTION_TITLES: Record<number, string> = {
  1: 'Кто вы и где',
  2: 'Чем вы занимаетесь',
  3: 'Дополнительные направления',
  4: 'Навыки и инструменты',
  5: 'Опыт и цены',
  6: 'Занятость и приватность',
  7: 'О себе',
  8: 'Фотография',
};

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

/**
 * Шаг «Ваши работы».
 *
 * Одна работа — минимум, без которого заявку не принимают. Анкета, которая
 * перечисляет навыки и не показывает ничего, просит заказчика поверить
 * незнакомцу на слово; этот рынок существует ровно затем, чтобы так не было.
 *
 * Форма нарочно короткая: название, что это было, ссылка. Всё остальное —
 * скриншоты, роль, стоимость — добавляется потом в портфолио, и здесь бы
 * только мешало.
 */
function PortfolioStage({
  profile,
  onAdded,
}: {
  profile: OwnProfile;
  onAdded: () => Promise<void>;
}) {
  const [items, setItems] = useState<PortfolioCard[] | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [work, setWork] = useState({
    title: '',
    short_description: '',
    description: '',
    category_slug: '',
    project_url: '',
    completed_on: '',
  });
  // Работу надо чем-то показать: ссылкой или картинкой. Одно из двух —
  // обязательно, иначе её нельзя опубликовать, а неопубликованную никто не
  // увидит. У дизайнера сайта может не быть вовсе, поэтому не только ссылка.
  const [shot, setShot] = useState<File | null>(null);
  const shotInput = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    get<PortfolioCard[]>('/portfolio')
      .then(setItems)
      .catch(() => setItems([]));
  }, []);

  useEffect(() => {
    load();
    get<Category[]>('/taxonomy/categories')
      .then(setCategories)
      .catch(() => setCategories([]));
  }, [load]);

  async function add() {
    setBusy(true);
    setFields({});
    setError('');
    try {
      const created = await post<{ id: string }>('/portfolio', {
        title: work.title.trim(),
        short_description: work.short_description.trim(),
        description: work.description.trim(),
        category_slug: work.category_slug,
        project_url: work.project_url.trim(),
        demo_status: work.project_url.trim() ? 'live' : 'none',
        completed_on: work.completed_on || undefined,
        // Навыки человек только что выбрал на прошлом шаге; спрашивать их ещё
        // раз здесь — лишний экран. Поправить набор можно потом в портфолио.
        technologies: (profile.skills ?? []).map((skill) => skill.slug).slice(0, 10),
      });
      if (shot) {
        const form = new FormData();
        form.set('image', shot);
        await upload(`/portfolio/${created.id}/images`, form);
      }
      // Опубликовать сразу: работа, которую никто не видит, заказчику ничего
      // не показывает — а именно за этим её и просили добавить.
      await post(`/portfolio/${created.id}/publish`, { published: true });
      setWork({ title: '', short_description: '', description: '', category_slug: '', project_url: '', completed_on: '' });
      setShot(null);
      if (shotInput.current) shotInput.current.value = '';
      setAdding(false);
      load();
      await onAdded();
    } catch (failure) {
      if (failure instanceof ApiFailure) {
        setFields(failure.fields);
        setError(Object.keys(failure.fields).length ? 'Проверьте отмеченные поля.' : failure.message);
      } else {
        setError('Не удалось сохранить. Проверьте подключение.');
      }
    } finally {
      setBusy(false);
    }
  }

  const samples = profile.onboarding?.work_samples ?? 0;
  const ready =
    work.title.trim().length >= 3 &&
    work.description.trim().length >= 40 &&
    Boolean(work.category_slug) &&
    (Boolean(work.project_url.trim()) || Boolean(shot));

  return (
    <div className="av-stack">
      {samples === 0 ? (
        <div className={styles.notice}>
          <p className="av-small av-strong">Нужна хотя бы одна работа</p>
          <p className="av-small">
            Подойдёт что угодно, что вы сделали: сайт, макет, текст, ролик, настроенная реклама.
            Заказы, выполненные на AVERIX, попадают сюда сами — но первый нужно показать самому.
          </p>
        </div>
      ) : null}

      {items === null ? (
        <Skeleton height={80} />
      ) : items.length > 0 ? (
        <ul className={styles.works}>
          {items.map((item) => (
            <li key={item.id} className={styles.work}>
              <span className="av-small av-strong">{item.title}</span>
              <span className="av-xs av-faint">
                {item.excerpt || 'Без описания'}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      {adding ? (
        <div className="av-stack-sm">
          {error ? (
            <p className={styles.alert} role="alert">
              {error}
            </p>
          ) : null}
          <Input
            label="Что вы сделали"
            placeholder="Например: логотип и вывеска для кофейни"
            value={work.title}
            error={fields.title}
            onChange={(event) => setWork((current) => ({ ...current, title: event.target.value }))}
          />
          <Select
            label="Направление"
            value={work.category_slug}
            error={fields.category_slug}
            onChange={(event) => setWork((current) => ({ ...current, category_slug: event.target.value }))}
          >
            <option value="">Выберите</option>
            {categories.map((category) => (
              <option key={category.slug} value={category.slug}>
                {category.name}
              </option>
            ))}
          </Select>
          <Input
            label="Коротко, одной строкой"
            placeholder="Айдентика для кофейни: логотип, вывеска, стаканы"
            value={work.short_description}
            error={fields.short_description}
            onChange={(event) => setWork((current) => ({ ...current, short_description: event.target.value }))}
          />
          <Textarea
            label="Что именно вы делали"
            hint="Задача, что вы сделали и что получилось. Несколько предложений достаточно."
            rows={5}
            max={4000}
            value={work.description}
            error={fields.description}
            onChange={(event) => setWork((current) => ({ ...current, description: event.target.value }))}
          />
          <Input
            label="Ссылка на работу"
            placeholder="https://"
            hint="Сайт, витрина, репозиторий или папка с примерами."
            value={work.project_url}
            error={fields.project_url}
            onChange={(event) => setWork((current) => ({ ...current, project_url: event.target.value }))}
          />

          <div className="av-stack-sm">
            <p className="av-small av-muted">
              Ссылки нет? Приложите изображение — скриншот, фотографию макета, кадр из ролика. Нужно
              хотя бы одно из двух: иначе работу нечем показать.
            </p>
            <input
              ref={shotInput}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              hidden
              onChange={(event) => setShot(event.target.files?.[0] ?? null)}
            />
            <div className="av-row av-wrap">
              <Button variant="secondary" size="sm" onClick={() => shotInput.current?.click()}>
                {shot ? 'Заменить изображение' : 'Приложить изображение'}
              </Button>
              {shot ? <span className="av-xs av-faint">{shot.name}</span> : null}
            </div>
          </div>
          <Input
            label="Когда закончили"
            type="date"
            value={work.completed_on}
            error={fields.completed_on}
            onChange={(event) => setWork((current) => ({ ...current, completed_on: event.target.value }))}
          />
          <div className="av-row av-wrap">
            <Button loading={busy} disabled={!ready} onClick={() => void add()}>
              Сохранить работу
            </Button>
            <Button variant="ghost" onClick={() => setAdding(false)}>
              Отмена
            </Button>
          </div>
        </div>
      ) : (
        <div>
          <Button variant={samples === 0 ? 'primary' : 'secondary'} onClick={() => setAdding(true)}>
            {samples === 0 ? 'Добавить работу' : 'Добавить ещё одну'}
          </Button>
        </div>
      )}
    </div>
  );
}

/** Сводка перед отправкой: то же, что увидит администратор. */
function Summary({ profile, draft }: { profile: OwnProfile; draft: Draft }) {
  const rows: { label: string; value: string }[] = [
    { label: 'Имя', value: draft.full_name || profile.full_name },
    { label: 'Где вы', value: [draft.city, draft.country_code].filter(Boolean).join(', ') || '—' },
    { label: 'Профессия', value: profile.primary_specialisation?.name ?? '—' },
    { label: 'Заголовок', value: draft.professional_title || '—' },
    { label: 'Навыки', value: draft.technologies.map((item) => item.name).join(', ') || '—' },
    { label: 'Опыт', value: EXPERIENCE[draft.experience_level] ?? draft.experience_level },
    {
      label: 'Ставка',
      value: draft.hourly_rate ? `${draft.hourly_rate} ${draft.currency} в час` : 'не указана',
    },
    { label: 'Занятость', value: AVAILABILITY[draft.availability] ?? draft.availability },
    { label: 'Работ в портфолио', value: String(profile.onboarding?.work_samples ?? 0) },
  ];

  return (
    <div className={styles.summary}>
      {rows.map((row) => (
        <div key={row.label} className={styles.summaryRow}>
          <span className={styles.summaryLabel}>{row.label}</span>
          <span className={styles.summaryValue}>{row.value}</span>
        </div>
      ))}
      <div className={styles.summaryRow}>
        <span className={styles.summaryLabel}>О себе</span>
        <span className={styles.summaryValue}>{draft.bio || '—'}</span>
      </div>
    </div>
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
