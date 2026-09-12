'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import styles from './landing.module.css';
import { Wordmark } from '@/components/nav/Logo';
import { Button, ButtonLink } from '@/components/ui/Button';
import { IconCheck, IconGitHub, IconShield } from '@/components/ui/Icon';
import { useSession } from '@/lib/session';
import { defaultHome } from '@/components/nav/TopBar';

export default function Landing() {
  const { session, loading } = useSession();
  const router = useRouter();

  // A signed-in person does not need the pitch.
  useEffect(() => {
    if (!loading && session) router.replace(defaultHome(session.active_role));
  }, [loading, session, router]);

  return (
    <main id="main" className={styles.page}>
      <header className={styles.header}>
        <Wordmark size={20} />
        <div className="av-row">
          <Link href="/login" className={styles.signIn}>
            Sign in
          </Link>
          <Button size="sm" onClick={() => router.push('/register')}>
            Join
          </Button>
        </div>
      </header>

      <section className={styles.hero}>
        <p className={styles.eyebrow}>For clients and developers</p>
        <h1 className={styles.title}>
          Hire developers who can <span className={styles.accent}>show the work</span>
        </h1>
        <p className={styles.lede}>
          Every finished contract on AVERIX attaches itself to the developer&rsquo;s profile — with
          the client&rsquo;s review, the technologies used and the delivery date. It cannot be
          written by hand, which is what makes it worth reading.
        </p>
        <div className={styles.actions}>
          <ButtonLink href="/register?role=client" size="lg">
            Post a project
          </ButtonLink>
          <ButtonLink href="/register?role=developer" size="lg" variant="secondary">
            Find work
          </ButtonLink>
        </div>
      </section>

      <section className={styles.points}>
        {[
          {
            icon: <IconShield size={18} />,
            title: 'Verified history, not claims',
            body: 'Completed AVERIX contracts appear on a profile automatically and are marked as verified. Self-declared portfolio work is shown separately, and labelled as such.',
          },
          {
            icon: <IconCheck size={18} />,
            title: 'Projects reach the right people',
            body: 'A Telegram bot in Python reaches Telegram and Python developers — not every designer on the platform. Matching explains itself: which requirements you meet, and which you do not.',
          },
          {
            icon: <IconGitHub size={18} />,
            title: 'GitHub, read honestly',
            body: 'Connect your account and AVERIX reads your public repositories for the technologies you actually use. Code share is shown as code share — never converted into a competence score.',
          },
        ].map((point) => (
          <article key={point.title} className={styles.point}>
            <span className={styles.pointIcon}>{point.icon}</span>
            <h2 className={styles.pointTitle}>{point.title}</h2>
            <p className={styles.pointBody}>{point.body}</p>
          </article>
        ))}
      </section>

      <footer className={styles.footer}>
        <Wordmark size={16} />
        <p className="av-small av-faint">
          A marketplace for software work. AVERIX holds no funds and makes no escrow claim.
        </p>
      </footer>
    </main>
  );
}
