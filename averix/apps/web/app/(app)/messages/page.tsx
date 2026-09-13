'use client';

import { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import styles from './messages.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconMessage, IconSend, IconArrowLeft } from '@/components/ui/Icon';
import { get, post } from '@/lib/api';
import { clockTime, timeAgo } from '@/lib/format';
import { useRealtime } from '@/lib/realtime';
import type { ConversationCard, Message } from '@/lib/types';

function Messages() {
  const params = useSearchParams();
  const [threads, setThreads] = useState<ConversationCard[] | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  const loadThreads = useCallback(async () => {
    try {
      setThreads(await get<ConversationCard[]>('/conversations'));
    } catch {
      setThreads([]);
    }
  }, []);

  const openThread = useCallback(async (id: string) => {
    setActive(id);
    setMessages(null);
    try {
      const page = await get<{ messages: Message[] }>(`/conversations/${id}/messages`);
      setMessages(page.messages);
      await post(`/conversations/${id}/read`);
    } catch {
      setMessages([]);
    }
  }, []);

  useEffect(() => {
    void loadThreads();
  }, [loadThreads]);

  // A contract's workspace links straight into its thread.
  useEffect(() => {
    if (!threads?.length) return;
    const direct = params.get('thread');
    if (direct && threads.some((thread) => thread.id === direct)) {
      void openThread(direct);
      return;
    }
    const contract = params.get('contract');
    if (!contract) return;
    const found = threads.find((thread) => thread.contract_id === contract);
    if (found) void openThread(found.id);
  }, [params, threads, openThread]);

  useRealtime((event) => {
    if (event.type === 'message' && event.message) {
      const incoming = event.message;
      if (incoming.conversation_id === active) {
        setMessages((current) =>
          current && !current.some((message) => message.id === incoming.id)
            ? [...current, incoming]
            : current,
        );
      }
      void loadThreads();
    }
  });

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages]);

  async function send() {
    if (!active || !draft.trim()) return;
    setSending(true);
    try {
      const message = await post<Message>(`/conversations/${active}/messages`, { body: draft.trim() });
      setMessages((current) => (current ? [...current, message] : [message]));
      setDraft('');
    } finally {
      setSending(false);
    }
  }

  const thread = threads?.find((item) => item.id === active) ?? null;

  return (
    <>
      <TopBar
        title={thread ? thread.counterparty.full_name : undefined}
        back={thread ? true : undefined}
        action={undefined}
      />

      <div className={styles.layout}>
        <aside className={[styles.list, active ? styles.listHidden : ''].join(' ')}>
          <div className="av-page av-stack-sm">
            <h1 className={styles.heading}>Сообщения</h1>
            {threads === null ? (
              <SkeletonList count={3} />
            ) : threads.length === 0 ? (
              <EmptyState
                icon={<IconMessage size={20} />}
                title="Диалогов пока нет"
                description="Переписка привязана к работе: диалог открывается, когда вы отправляете или получаете отклик, и когда заключена сделка."
              />
            ) : (
              threads.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={[styles.thread, active === item.id ? styles.threadActive : ''].join(' ')}
                  onClick={() => void openThread(item.id)}
                >
                  <Avatar src={item.counterparty.photo_url} name={item.counterparty.full_name} size={48} />
                  <div className={styles.threadBody}>
                    <div className={styles.threadTop}>
                      <span className="av-strong">{item.counterparty.full_name}</span>
                      <span className="av-xs av-faint">{timeAgo(item.last_message_at)}</span>
                    </div>
                    <p className="av-small av-muted av-clamp-2">
                      {item.preview || item.project_title || 'Сообщений пока нет'}
                    </p>
                  </div>
                  {item.unread_count > 0 ? (
                    <span className={styles.unread}>{item.unread_count}</span>
                  ) : null}
                </button>
              ))
            )}
          </div>
        </aside>

        <section className={[styles.thread_panel, active ? styles.panelOpen : ''].join(' ')}>
          {!active ? (
            <div className={styles.placeholder}>
              <IconMessage size={28} />
              <p className="av-muted">Выберите диалог, чтобы прочитать.</p>
            </div>
          ) : (
            <>
              <header className={styles.threadHeader}>
                <button
                  type="button"
                  className={styles.backButton}
                  onClick={() => setActive(null)}
                  aria-label="К списку диалогов"
                >
                  <IconArrowLeft size={18} />
                </button>
                <Avatar src={thread?.counterparty.photo_url} name={thread?.counterparty.full_name} size={32} />
                <div className="av-grow">
                  <p className="av-strong">{thread?.counterparty.full_name}</p>
                  <p className="av-xs av-faint">{thread?.project_title ?? thread?.subject}</p>
                </div>
              </header>

              <div className={styles.stream}>
                {messages === null ? (
                  <SkeletonList count={2} />
                ) : (
                  messages.map((message) =>
                    message.kind === 'system' ? (
                      <p key={message.id} className={styles.system}>
                        {systemText(message)} · {clockTime(message.created_at)}
                      </p>
                    ) : (
                      <div
                        key={message.id}
                        className={[styles.bubbleRow, message.is_mine ? styles.mine : ''].join(' ')}
                      >
                        <div className={styles.bubble}>
                          {message.is_deleted ? (
                            <span className="av-faint">Сообщение удалено</span>
                          ) : (
                            message.body
                          )}
                          <span className={styles.time}>{clockTime(message.created_at)}</span>
                        </div>
                      </div>
                    ),
                  )
                )}
                <div ref={bottom} />
              </div>

              <form
                className={styles.composer}
                onSubmit={(event) => {
                  event.preventDefault();
                  void send();
                }}
              >
                <textarea
                  className={styles.input}
                  placeholder="Напишите сообщение"
                  rows={1}
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault();
                      void send();
                    }
                  }}
                />
                <Button
                  type="submit"
                  size="md"
                  loading={sending}
                  disabled={!draft.trim()}
                  icon={<IconSend size={18} />}
                  aria-label="Отправить"
                />
              </form>
            </>
          )}
        </section>
      </div>
    </>
  );
}

function systemText(message: Message) {
  const event = message.system_event ?? '';
  const map: Record<string, string> = {
    'contract.signed': 'Сделка заключена',
    'contract.completed': 'Сделка завершена',
    'contract.cancelled': 'Сделка отменена',
    'milestone.funded': 'Этап оплачен в резерв',
    'milestone.in_progress': 'Работа начата',
    'milestone.submitted': 'Работа сдана на проверку',
    'milestone.revision_requested': 'Запрошена доработка',
    'milestone.approved': 'Этап принят',
    'milestone.released': 'Оплата выплачена',
    'milestone.disputed': 'Открыт спор',
    'milestone.resolved': 'Спор разрешён платформой',
    'milestone.cancelled': 'Этап отменён',
  };
  return map[event] ?? event.replace(/[._]/g, ' ');
}

export default function MessagesPage() {
  return (
    <Suspense fallback={null}>
      <Messages />
    </Suspense>
  );
}
