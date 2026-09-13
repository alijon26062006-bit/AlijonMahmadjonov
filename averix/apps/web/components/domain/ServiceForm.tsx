'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import styles from './ServiceForm.module.css';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { ChoiceChip, Input, Select, Textarea } from '@/components/ui/Field';
import { IconClose } from '@/components/ui/Icon';
import { ApiFailure, get, patch, post } from '@/lib/api';
import { CURRENCIES, SECTORS } from '@/lib/labels';
import type { Category, Service, Skill } from '@/lib/types';

type TierDraft = { name: string; price: string; delivery_days: string; revisions: string; includes: string };

const BLANK_TIER: TierDraft = { name: '', price: '', delivery_days: '', revisions: '1', includes: '' };

/**
 * Форма услуги — одна и та же для создания и правки.
 *
 * Пакетов до трёх, и цены должны расти: «Базовый» дороже «Расширенного» —
 * это не выбор, а ошибка, и сервер её не примет.
 */
export function ServiceForm({ existing }: { existing?: Service }) {
  const router = useRouter();

  const [sector, setSector] = useState('');
  const [categorySlug, setCategorySlug] = useState(existing?.category.slug ?? '');
  const [title, setTitle] = useState(existing?.title ?? '');
  const [summary, setSummary] = useState(existing?.summary ?? '');
  const [description, setDescription] = useState(existing?.description ?? '');
  const [currency, setCurrency] = useState(existing?.currency ?? 'RUB');
  const [revisions, setRevisions] = useState(String(existing?.revisions ?? 1));
  const [skills, setSkills] = useState<string[]>(existing?.skills?.map((skill) => skill.slug) ?? []);
  const [tiers, setTiers] = useState<TierDraft[]>(
    existing?.tiers?.length
      ? existing.tiers.map((tier) => ({
          name: tier.name,
          price: String(Math.round(tier.price_minor / 100)),
          delivery_days: String(tier.delivery_days),
          revisions: String(tier.revisions),
          includes: (tier.includes ?? []).join('\n'),
        }))
      : [{ ...BLANK_TIER, name: 'Базовый' }],
  );

  const [tree, setTree] = useState<Category[]>([]);
  const [suggested, setSuggested] = useState<Skill[]>([]);
  const [skillQuery, setSkillQuery] = useState('');
  const [found, setFound] = useState<Skill[]>([]);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    get<Category[]>('/taxonomy/categories')
      .then((data) => {
        setTree(data);
        if (existing) {
          const owner = data.find((node) =>
            [node, ...(node.children ?? [])].some((child) =>
              [child, ...(child.children ?? [])].some((leaf) => leaf.slug === existing.category.slug),
            ),
          );
          if (owner) setSector(owner.slug);
        }
      })
      .catch(() => undefined);
  }, [existing]);

  useEffect(() => {
    if (!categorySlug) return;
    get<Skill[]>(`/taxonomy/categories/${categorySlug}/skills`)
      .then(setSuggested)
      .catch(() => setSuggested([]));
  }, [categorySlug]);

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

  const categories = tree.find((node) => node.slug === sector)?.children ?? [];

  function toggleSkill(slug: string) {
    setSkills((current) => (current.includes(slug) ? current.filter((item) => item !== slug) : [...current, slug]));
  }

  async function save(publish: boolean) {
    setBusy(true);
    setFields({});
    setMessage('');
    const body = {
      title: title.trim(),
      summary: summary.trim(),
      description: description.trim(),
      category_slug: categorySlug,
      currency,
      revisions: Number(revisions) || 0,
      skills,
      tiers: tiers
        .filter((tier) => tier.name.trim())
        .map((tier) => ({
          name: tier.name.trim(),
          price_minor: Math.round(Number(tier.price.replace(/[^\d.]/g, '')) * 100) || 0,
          delivery_days: Number(tier.delivery_days) || 0,
          revisions: Number(tier.revisions) || 0,
          includes: tier.includes
            .split('\n')
            .map((line) => line.trim())
            .filter(Boolean),
        })),
      portfolio_ids: [],
    };
    try {
      const saved = existing
        ? await patch<Service>(`/services/${existing.id}`, body)
        : await post<Service>('/services', body);
      if (publish) await post(`/services/${saved.id}/publish`);
      router.replace(`/services/${saved.id}`);
    } catch (error) {
      if (error instanceof ApiFailure) {
        setFields(error.fields);
        setMessage(Object.keys(error.fields).length ? 'Проверьте отмеченные поля.' : error.message);
      } else {
        setMessage('Не удалось сохранить услугу.');
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <div className="av-stack">
        {message ? (
          <p className={styles.alert} role="alert">
            {message}
          </p>
        ) : null}

        <div className="av-stack-sm">
          <p className="av-small av-strong">Направление</p>
          <div className={styles.chips}>
            {SECTORS.map((item) => (
              <ChoiceChip
                key={item.slug}
                selected={sector === item.slug}
                onToggle={() => {
                  setSector(item.slug);
                  setCategorySlug('');
                }}
              >
                {item.name}
              </ChoiceChip>
            ))}
          </div>
        </div>

        {categories.length ? (
          <div className="av-stack-sm">
            <p className="av-small av-strong">Категория</p>
            <div className={styles.chips}>
              {categories.flatMap((category) => [category, ...(category.children ?? [])]).map((category) => (
                <ChoiceChip
                  key={category.slug}
                  selected={categorySlug === category.slug}
                  onToggle={() => setCategorySlug(category.slug)}
                >
                  {category.name}
                </ChoiceChip>
              ))}
            </div>
            {fields.category_slug ? <p className={styles.alert}>{fields.category_slug}</p> : null}
          </div>
        ) : null}

        <Input
          label="Название услуги"
          placeholder="Сделаю логотип и базовый фирменный стиль"
          hint="От 8 до 120 символов. Начните с глагола — так понятнее, что вы делаете."
          value={title}
          error={fields.title}
          onChange={(event) => setTitle(event.target.value)}
        />
        <Input
          label="Короткое описание"
          placeholder="Одно предложение о результате"
          value={summary}
          error={fields.summary}
          onChange={(event) => setSummary(event.target.value)}
        />
        <Textarea
          label="Подробное описание"
          placeholder="Что именно получает заказчик, как проходит работа, что нужно от него."
          hint="Не меньше 80 символов."
          max={10000}
          rows={8}
          value={description}
          error={fields.description}
          onChange={(event) => setDescription(event.target.value)}
        />

        <div className="av-row">
          <Select label="Валюта" value={currency} onChange={(event) => setCurrency(event.target.value)}>
            {CURRENCIES.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </Select>
          <Input
            label="Правок по умолчанию"
            inputMode="numeric"
            value={revisions}
            error={fields.revisions}
            onChange={(event) => setRevisions(event.target.value)}
          />
        </div>

        <div className="av-stack-sm">
          <p className="av-small av-strong">Пакеты</p>
          {fields.tiers ? <p className={styles.alert}>{fields.tiers}</p> : null}
          {tiers.map((tier, index) => (
            <div key={index} className={styles.tier}>
              <div className="av-row-between">
                <span className="av-small av-strong">Пакет {index + 1}</span>
                {tiers.length > 1 ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label="Убрать пакет"
                    icon={<IconClose size={15} />}
                    onClick={() => setTiers(tiers.filter((_, i) => i !== index))}
                  />
                ) : null}
              </div>
              <Input
                label="Название"
                placeholder="Базовый"
                value={tier.name}
                onChange={(event) => {
                  const next = [...tiers];
                  next[index] = { ...next[index], name: event.target.value };
                  setTiers(next);
                }}
              />
              <div className="av-row">
                <Input
                  label="Цена"
                  inputMode="numeric"
                  value={tier.price}
                  onChange={(event) => {
                    const next = [...tiers];
                    next[index] = { ...next[index], price: event.target.value };
                    setTiers(next);
                  }}
                />
                <Input
                  label="Срок, дней"
                  inputMode="numeric"
                  value={tier.delivery_days}
                  onChange={(event) => {
                    const next = [...tiers];
                    next[index] = { ...next[index], delivery_days: event.target.value };
                    setTiers(next);
                  }}
                />
                <Input
                  label="Правок"
                  inputMode="numeric"
                  value={tier.revisions}
                  onChange={(event) => {
                    const next = [...tiers];
                    next[index] = { ...next[index], revisions: event.target.value };
                    setTiers(next);
                  }}
                />
              </div>
              <Textarea
                label="Что входит"
                optional
                hint="По одному пункту на строку."
                rows={3}
                max={1000}
                value={tier.includes}
                onChange={(event) => {
                  const next = [...tiers];
                  next[index] = { ...next[index], includes: event.target.value };
                  setTiers(next);
                }}
              />
            </div>
          ))}
          {tiers.length < 3 ? (
            <Button variant="secondary" size="sm" onClick={() => setTiers([...tiers, { ...BLANK_TIER }])}>
              Добавить пакет
            </Button>
          ) : null}
          <p className="av-xs av-faint">Цены должны идти по возрастанию: следующий пакет дороже предыдущего.</p>
        </div>

        <div className="av-stack-sm">
          <p className="av-small av-strong">Навыки</p>
          {suggested.length ? (
            <div className={styles.chips}>
              {suggested.map((skill) => (
                <ChoiceChip key={skill.slug} selected={skills.includes(skill.slug)} onToggle={() => toggleSkill(skill.slug)}>
                  {skill.name}
                </ChoiceChip>
              ))}
            </div>
          ) : null}
          <Input
            label="Найти навык"
            optional
            value={skillQuery}
            onChange={(event) => setSkillQuery(event.target.value)}
          />
          {found.length ? (
            <div className={styles.chips}>
              {found.map((skill) => (
                <ChoiceChip key={skill.slug} selected={skills.includes(skill.slug)} onToggle={() => toggleSkill(skill.slug)}>
                  {skill.name}
                </ChoiceChip>
              ))}
            </div>
          ) : null}
          {fields.skills ? <p className={styles.alert}>{fields.skills}</p> : null}
        </div>

        <div className="av-row">
          <Button variant="secondary" loading={busy} onClick={() => void save(false)}>
            Сохранить черновик
          </Button>
          <Button loading={busy} onClick={() => void save(true)}>
            Опубликовать
          </Button>
        </div>
      </div>
    </Card>
  );
}
