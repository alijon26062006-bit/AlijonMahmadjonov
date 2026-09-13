'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import styles from './new.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { ChoiceChip, Input, Select, Textarea } from '@/components/ui/Field';
import { IconClose } from '@/components/ui/Icon';
import { ApiFailure, get, patch, post } from '@/lib/api';
import { budgetRange } from '@/lib/format';
import { BUDGET_TYPE, CURRENCIES, EXPERIENCE, SECTORS, STARTS, VISIBILITY } from '@/lib/labels';
import type { Category, Project, Skill } from '@/lib/types';

const TOTAL = 5;

type Draft = {
  sector: string;
  category_slug: string;
  title: string;
  summary: string;
  description: string;
  features: { title: string; detail: string }[];
  required_skills: string[];
  optional_skills: string[];
  budget_type: string;
  budget_min: string;
  budget_max: string;
  currency: string;
  duration_days: string;
  deadline: string;
  starts: string;
  experience_wanted: string;
  visibility: string;
};

const EMPTY: Draft = {
  sector: '',
  category_slug: '',
  title: '',
  summary: '',
  description: '',
  features: [],
  required_skills: [],
  optional_skills: [],
  budget_type: 'range',
  budget_min: '',
  budget_max: '',
  currency: 'RUB',
  duration_days: '',
  deadline: '',
  starts: 'flexible',
  experience_wanted: 'any',
  visibility: 'public',
};

function NewProject() {
  const router = useRouter();
  const params = useSearchParams();
  const editID = params.get('edit');

  const [step, setStep] = useState(1);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [tree, setTree] = useState<Category[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [skillQuery, setSkillQuery] = useState('');
  const [found, setFound] = useState<Skill[]>([]);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    get<Category[]>('/taxonomy/categories')
      .then(setTree)
      .catch(() => undefined);
  }, []);

  // Правка черновика: подставляем то, что уже написано.
  useEffect(() => {
    if (!editID) return;
    get<Project[]>('/projects/mine/list')
      .then((list) => {
        const existing = list.find((project) => project.id === editID);
        if (!existing) return;
        setDraft((current) => ({
          ...current,
          category_slug: existing.category.slug,
          sector: existing.category.path?.split('/')[0] ?? '',
          title: existing.title,
          summary: existing.summary ?? '',
          description: existing.description,
          features: (existing.features ?? []).map((feature) => ({ title: feature.title, detail: feature.detail ?? '' })),
          required_skills: existing.skills.map((skill) => skill.slug),
          budget_type: existing.budget.type || current.budget_type,
          budget_min: existing.budget.min_minor ? String(Math.round(existing.budget.min_minor / 100)) : '',
          budget_max: existing.budget.max_minor ? String(Math.round(existing.budget.max_minor / 100)) : '',
          currency: existing.budget.currency || current.currency,
          duration_days: existing.duration_days ? String(existing.duration_days) : '',
          experience_wanted: existing.experience_wanted || current.experience_wanted,
        }));
      })
      .catch(() => undefined);
  }, [editID]);

  const categories = useMemo(() => {
    const sector = tree.find((node) => node.slug === draft.sector);
    return sector?.children ?? [];
  }, [tree, draft.sector]);

  useEffect(() => {
    if (!draft.category_slug) return;
    get<Skill[]>(`/taxonomy/categories/${draft.category_slug}/skills`)
      .then(setSkills)
      .catch(() => setSkills([]));
  }, [draft.category_slug]);

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

  function set<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function toggleSkill(slug: string) {
    set(
      'required_skills',
      draft.required_skills.includes(slug)
        ? draft.required_skills.filter((item) => item !== slug)
        : [...draft.required_skills, slug],
    );
  }

  const minor = (value: string) => {
    const number = Number(value.replace(/[^\d.]/g, ''));
    return Number.isFinite(number) && number > 0 ? Math.round(number * 100) : null;
  };

  async function submit(publish: boolean) {
    setBusy(true);
    setFields({});
    setMessage('');
    const body = {
      title: draft.title.trim(),
      summary: draft.summary.trim(),
      description: draft.description.trim(),
      category_slug: draft.category_slug,
      required_skills: draft.required_skills,
      optional_skills: draft.optional_skills,
      features: draft.features.filter((feature) => feature.title.trim()),
      budget_type: draft.budget_type,
      budget_min_minor: minor(draft.budget_min),
      budget_max_minor: minor(draft.budget_max),
      currency: draft.currency,
      duration_days: draft.duration_days ? Number(draft.duration_days) : null,
      deadline: draft.deadline || null,
      starts: draft.starts,
      experience_wanted: draft.experience_wanted,
      visibility: draft.visibility,
      publish,
    };
    try {
      const project = editID
        ? await patch<Project>(`/projects/${editID}`, body)
        : await post<Project>('/projects', body);
      if (editID && publish) await post(`/projects/${editID}/publish`);
      router.replace(publish ? `/projects/${project.slug}/proposals` : `/projects/${project.slug}`);
    } catch (error) {
      if (error instanceof ApiFailure) {
        setFields(error.fields);
        setMessage(Object.keys(error.fields).length ? 'Проверьте отмеченные поля.' : error.message);
        if (error.fields.title || error.fields.category_slug) setStep(1);
        else if (error.fields.description || error.fields.summary) setStep(2);
        else if (error.fields.required_skills) setStep(3);
        else if (Object.keys(error.fields).some((key) => key.startsWith('budget') || key === 'duration_days')) setStep(4);
      } else {
        setMessage('Не удалось сохранить заказ. Проверьте подключение.');
      }
    } finally {
      setBusy(false);
    }
  }

  const canContinue = (() => {
    switch (step) {
      case 1:
        return Boolean(draft.category_slug) && draft.title.trim().length >= 10;
      case 2:
        return draft.description.trim().length >= 80;
      case 3:
        return draft.required_skills.length > 0;
      case 4:
        return Boolean(minor(draft.budget_min) || minor(draft.budget_max));
      default:
        return true;
    }
  })();

  return (
    <>
      <TopBar back="/dashboard" title={editID ? 'Правка заказа' : 'Новый заказ'} />
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
                <div className="av-stack-sm">
                  <p className="av-small av-strong">Направление</p>
                  <div className={styles.grid}>
                    {SECTORS.map((sector) => (
                      <button
                        key={sector.slug}
                        type="button"
                        className={[styles.tile, draft.sector === sector.slug ? styles.tileActive : ''].join(' ')}
                        onClick={() => {
                          set('sector', sector.slug);
                          set('category_slug', '');
                        }}
                        aria-pressed={draft.sector === sector.slug}
                      >
                        <span className={styles.tileName}>{sector.name}</span>
                        <span className={styles.tileHint}>{sector.hint}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {categories.length ? (
                  <div className="av-stack-sm">
                    <p className="av-small av-strong">Что именно нужно</p>
                    <div className={styles.chips}>
                      {categories.flatMap((category) => [category, ...(category.children ?? [])]).map((category) => (
                        <ChoiceChip
                          key={category.slug}
                          selected={draft.category_slug === category.slug}
                          onToggle={() => set('category_slug', category.slug)}
                        >
                          {category.name}
                        </ChoiceChip>
                      ))}
                    </div>
                    {fields.category_slug ? <p className={styles.alert}>{fields.category_slug}</p> : null}
                  </div>
                ) : null}

                <Input
                  label="Название заказа"
                  placeholder="Например: Логотип и фирменный стиль для кофейни"
                  hint="Коротко и по делу — это первое, что видит исполнитель."
                  value={draft.title}
                  error={fields.title}
                  onChange={(event) => set('title', event.target.value)}
                />
              </div>
            ) : null}

            {step === 2 ? (
              <div className="av-stack">
                <Input
                  label="Короткое описание"
                  optional
                  placeholder="Одно предложение о задаче"
                  value={draft.summary}
                  error={fields.summary}
                  onChange={(event) => set('summary', event.target.value)}
                />
                <Textarea
                  label="Подробное описание"
                  placeholder="Что нужно сделать, для кого, в каком виде принимаете результат. Чем конкретнее — тем точнее отклики."
                  hint="Не меньше 80 символов."
                  max={20000}
                  rows={10}
                  value={draft.description}
                  error={fields.description}
                  onChange={(event) => set('description', event.target.value)}
                />

                <div className="av-stack-sm">
                  <p className="av-small av-strong">Что входит в работу</p>
                  {draft.features.map((feature, index) => (
                    <div key={index} className={styles.featureRow}>
                      <Input
                        label={`Пункт ${index + 1}`}
                        value={feature.title}
                        onChange={(event) => {
                          const next = [...draft.features];
                          next[index] = { ...next[index], title: event.target.value };
                          set('features', next);
                        }}
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label="Убрать пункт"
                        icon={<IconClose size={16} />}
                        onClick={() => set('features', draft.features.filter((_, i) => i !== index))}
                      />
                    </div>
                  ))}
                  {draft.features.length < 12 ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => set('features', [...draft.features, { title: '', detail: '' }])}
                    >
                      Добавить пункт
                    </Button>
                  ) : null}
                </div>
              </div>
            ) : null}

            {step === 3 ? (
              <div className="av-stack">
                {skills.length ? (
                  <div className="av-stack-sm">
                    <p className="av-small av-strong">Обычно нужны для такой работы</p>
                    <div className={styles.chips}>
                      {skills.map((skill) => (
                        <ChoiceChip
                          key={skill.slug}
                          selected={draft.required_skills.includes(skill.slug)}
                          onToggle={() => toggleSkill(skill.slug)}
                        >
                          {skill.name}
                        </ChoiceChip>
                      ))}
                    </div>
                  </div>
                ) : null}
                <Input
                  label="Найти навык"
                  placeholder="Figma, копирайтинг, Python…"
                  value={skillQuery}
                  onChange={(event) => setSkillQuery(event.target.value)}
                />
                {found.length ? (
                  <div className={styles.chips}>
                    {found.map((skill) => (
                      <ChoiceChip
                        key={skill.slug}
                        selected={draft.required_skills.includes(skill.slug)}
                        onToggle={() => toggleSkill(skill.slug)}
                      >
                        {skill.name}
                      </ChoiceChip>
                    ))}
                  </div>
                ) : null}
                {fields.required_skills ? <p className={styles.alert}>{fields.required_skills}</p> : null}
                <p className="av-small av-faint">
                  По этим навыкам заказ попадёт в ленту тем, кто действительно ими владеет, — а не всем
                  подряд.
                </p>
              </div>
            ) : null}

            {step === 4 ? (
              <div className="av-stack">
                <Select
                  label="Тип бюджета"
                  value={draft.budget_type}
                  error={fields.budget_type}
                  onChange={(event) => set('budget_type', event.target.value)}
                >
                  {Object.entries(BUDGET_TYPE).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </Select>
                <Select label="Валюта" value={draft.currency} onChange={(event) => set('currency', event.target.value)}>
                  {CURRENCIES.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </Select>
                <div className="av-row">
                  <Input
                    label="От"
                    inputMode="numeric"
                    value={draft.budget_min}
                    error={fields.budget_min_minor}
                    onChange={(event) => set('budget_min', event.target.value)}
                  />
                  <Input
                    label="До"
                    inputMode="numeric"
                    value={draft.budget_max}
                    error={fields.budget_max_minor}
                    onChange={(event) => set('budget_max', event.target.value)}
                  />
                </div>
                <Input
                  label="Срок, дней"
                  optional
                  inputMode="numeric"
                  value={draft.duration_days}
                  error={fields.duration_days}
                  onChange={(event) => set('duration_days', event.target.value)}
                />
                <Input
                  label="Крайняя дата"
                  optional
                  type="date"
                  value={draft.deadline}
                  error={fields.deadline}
                  onChange={(event) => set('deadline', event.target.value)}
                />
                <Select label="Когда начинать" value={draft.starts} onChange={(event) => set('starts', event.target.value)}>
                  {Object.entries(STARTS).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </Select>
                <Select
                  label="Уровень исполнителя"
                  value={draft.experience_wanted}
                  onChange={(event) => set('experience_wanted', event.target.value)}
                >
                  {Object.entries(EXPERIENCE).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </Select>
              </div>
            ) : null}

            {step === 5 ? (
              <div className="av-stack">
                <div className={styles.summary}>
                  <div>
                    <span className="av-muted">Название</span>
                    <strong>{draft.title}</strong>
                  </div>
                  <div>
                    <span className="av-muted">Бюджет</span>
                    <strong>{budgetRange(minor(draft.budget_min), minor(draft.budget_max), draft.currency)}</strong>
                  </div>
                  <div>
                    <span className="av-muted">Навыки</span>
                    <strong>{draft.required_skills.length}</strong>
                  </div>
                </div>
                <Select
                  label="Кто видит заказ"
                  value={draft.visibility}
                  onChange={(event) => set('visibility', event.target.value)}
                >
                  {Object.entries(VISIBILITY).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </Select>
                <p className="av-small av-muted">
                  Публикация бесплатна. Деньги резервируются только по этапам, когда вы выберете
                  исполнителя и подтвердите сделку.
                </p>
              </div>
            ) : null}

            <div className={styles.actions}>
              {step > 1 ? (
                <Button variant="secondary" onClick={() => setStep(step - 1)}>
                  Назад
                </Button>
              ) : null}
              {step === TOTAL ? (
                <>
                  <Button variant="secondary" loading={busy} onClick={() => void submit(false)}>
                    Сохранить черновик
                  </Button>
                  <Button loading={busy} onClick={() => void submit(true)}>
                    Опубликовать
                  </Button>
                </>
              ) : (
                <Button disabled={!canContinue} onClick={() => setStep(step + 1)}>
                  Далее
                </Button>
              )}
            </div>
          </div>
        </Card>
      </div>
    </>
  );
}

const STEPS = [
  { title: 'Что нужно сделать', lede: 'Выберите направление и назовите задачу так, как назвали бы её знакомому.' },
  { title: 'Описание', lede: 'Чем понятнее написано, тем меньше уточняющих вопросов и лишних откликов.' },
  { title: 'Навыки', lede: 'По ним заказ находит нужных исполнителей.' },
  { title: 'Бюджет и сроки', lede: 'Вилка честнее, чем «договоримся»: на неё приходят те, кому цена подходит.' },
  { title: 'Проверьте и опубликуйте', lede: 'Черновик можно дописать позже — он виден только вам.' },
];

export default function NewProjectPage() {
  return (
    <Suspense fallback={null}>
      <NewProject />
    </Suspense>
  );
}
