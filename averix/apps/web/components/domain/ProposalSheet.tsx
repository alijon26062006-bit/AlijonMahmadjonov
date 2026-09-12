'use client';

import { useState } from 'react';
import styles from './ProposalSheet.module.css';
import { Sheet } from '@/components/ui/Sheet';
import { Button } from '@/components/ui/Button';
import { Input, Textarea } from '@/components/ui/Field';
import { ApiFailure, post } from '@/lib/api';
import { money } from '@/lib/format';
import type { Project } from '@/lib/types';

const MINIMUMS = { cover_letter: 120, approach: 120, relevant_experience: 60 };

/**
 * Writing a proposal.
 *
 * The floors are the product: "ready to do it" cannot be submitted, and the
 * form says why each section matters rather than only counting characters.
 * Three steps on a phone, because a five-field wall at 375px is abandoned.
 */
export function ProposalSheet({
  open,
  project,
  onClose,
  onSent,
}: {
  open: boolean;
  project: Project;
  onClose: () => void;
  onSent: () => void;
}) {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({
    amount: '',
    delivery_days: '',
    cover_letter: '',
    approach: '',
    relevant_experience: '',
    questions: '',
  });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  function update(key: keyof typeof form) {
    return (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((current) => ({ ...current, [key]: event.target.value }));
  }

  const amountMinor = Math.round(Number(form.amount.replace(/[^\d.]/g, '')) * 100);
  const fee = Math.round(amountMinor * 0.1);

  async function submit() {
    setBusy(true);
    setFields({});
    setMessage('');
    try {
      await post('/proposals', {
        project_id: project.id,
        amount_minor: amountMinor,
        currency: project.budget.currency || 'USD',
        delivery_days: Number(form.delivery_days),
        cover_letter: form.cover_letter.trim(),
        approach: form.approach.trim(),
        relevant_experience: form.relevant_experience.trim(),
        questions: form.questions.trim() || undefined,
      });
      onSent();
      setStep(0);
    } catch (error) {
      if (error instanceof ApiFailure) {
        setFields(error.fields);
        setMessage(Object.keys(error.fields).length ? 'Some sections need a little more.' : error.message);
        // Send the person to the step that holds the problem.
        if (error.fields.amount_minor || error.fields.delivery_days) setStep(0);
        else if (error.fields.cover_letter) setStep(1);
        else if (error.fields.approach || error.fields.relevant_experience) setStep(2);
      } else {
        setMessage("We couldn't send that. Please check your connection and try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  const steps = [
    {
      title: 'Your terms',
      valid: amountMinor > 0 && Number(form.delivery_days) > 0,
      body: (
        <div className="av-stack">
          <Input
            label={`Your price (${project.budget.currency || 'USD'})`}
            inputMode="decimal"
            placeholder="650"
            prefix="$"
            hint={`The client's budget: ${project.budget.display}`}
            value={form.amount}
            error={fields.amount_minor}
            onChange={update('amount')}
          />
          {amountMinor > 0 ? (
            <p className={styles.fee}>
              You quote <strong>{money(amountMinor, project.budget.currency)}</strong> · platform fee{' '}
              {money(fee, project.budget.currency)} · you receive{' '}
              <strong>{money(amountMinor - fee, project.budget.currency)}</strong>
            </p>
          ) : null}
          <Input
            label="Delivery time (days)"
            inputMode="numeric"
            placeholder="12"
            hint="From the day work starts, not from today."
            value={form.delivery_days}
            error={fields.delivery_days}
            onChange={update('delivery_days')}
          />
        </div>
      ),
    },
    {
      title: 'Why you',
      valid: form.cover_letter.trim().length >= MINIMUMS.cover_letter,
      body: (
        <Textarea
          label="Message to the client"
          placeholder="What you understood about this project, and why you are a good fit for it."
          hint="At least 120 characters. Clients read this first — a template gets skipped."
          max={4000}
          rows={8}
          value={form.cover_letter}
          error={fields.cover_letter}
          onChange={update('cover_letter')}
        />
      ),
    },
    {
      title: 'How you will do it',
      valid:
        form.approach.trim().length >= MINIMUMS.approach &&
        form.relevant_experience.trim().length >= MINIMUMS.relevant_experience,
      body: (
        <div className="av-stack">
          <Textarea
            label="Your approach"
            placeholder="The order you would build this in, and what you would agree before starting."
            hint="At least 120 characters."
            max={4000}
            rows={6}
            value={form.approach}
            error={fields.approach}
            onChange={update('approach')}
          />
          <Textarea
            label="Relevant experience"
            placeholder="The closest thing you have built before."
            hint="At least 60 characters."
            max={2000}
            rows={4}
            value={form.relevant_experience}
            error={fields.relevant_experience}
            onChange={update('relevant_experience')}
          />
          <Textarea
            label="Questions for the client"
            optional
            placeholder="Anything that would change your estimate."
            max={1000}
            rows={3}
            value={form.questions}
            onChange={update('questions')}
          />
        </div>
      ),
    },
  ];

  const current = steps[step];
  const last = step === steps.length - 1;

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Send a proposal"
      description={project.title}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={() => (step === 0 ? onClose() : setStep(step - 1))}>
            {step === 0 ? 'Cancel' : 'Back'}
          </Button>
          <Button
            loading={busy}
            disabled={!current.valid}
            onClick={() => (last ? void submit() : setStep(step + 1))}
          >
            {last ? 'Send proposal' : 'Continue'}
          </Button>
        </>
      }
    >
      <div className="av-stack">
        <ol className={styles.steps} aria-label="Progress">
          {steps.map((item, index) => (
            <li
              key={item.title}
              className={[
                styles.step,
                index === step ? styles.stepActive : '',
                index < step ? styles.stepDone : '',
              ].join(' ')}
            >
              <span className={styles.stepDot} aria-hidden="true" />
              {item.title}
            </li>
          ))}
        </ol>

        {message ? (
          <p className={styles.alert} role="alert">
            {message}
          </p>
        ) : null}

        {current.body}
      </div>
    </Sheet>
  );
}
