/** Профиль: имя, контакты, куда слать про заказ, выход. */
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { telegramLinkUrl, updateMe } from '../api/client';
import type { ShopConfig } from '../api/types';
import { Icon } from '../components/icons';
import { Empty, signOut, useAuth, useToast } from '../components/ui';

export default function ProfilePage({ cfg }: { cfg?: ShopConfig }) {
  const user = useAuth();
  const navigate = useNavigate();
  const { toast, node } = useToast();
  const [name, setName] = useState(user?.name ?? '');
  const [email, setEmail] = useState(user?.email ?? '');
  const [linking, setLinking] = useState(false);

  useEffect(() => {
    if (user) { setName(user.name); setEmail(user.email ?? ''); }
  }, [user]);

  if (!user) {
    return (
      <div className="page">
        <Empty icon="user" title="Вы не вошли"
               note="Вход нужен, чтобы оформлять заказы и следить за доставкой"
               action={{ label: 'Войти', to: '/login' }} />
      </div>
    );
  }

  const save = async (patch: Record<string, unknown>, note: string) => {
    try { await updateMe(patch); toast(note); }
    catch (e) { toast((e as Error).message || 'Не сохранилось'); }
  };

  const linkTelegram = async () => {
    setLinking(true);
    try { window.open(await telegramLinkUrl(), '_blank', 'noopener'); }
    catch { toast('Не получилось, попробуйте ещё раз'); }
    setLinking(false);
  };

  return (
    <div className="page fade-in" style={{ maxWidth: 620 }}>
      <h1>Профиль</h1>

      <div className="stack" style={{ marginTop: 24 }}>
        <div className="field">
          <label htmlFor="name">Как к вам обращаться</label>
          <input id="name" className="input" value={name}
                 onChange={(e) => setName(e.target.value)}
                 onBlur={() => name !== user.name && save({ name }, 'Имя сохранено')} />
        </div>

        <div className="field">
          <label htmlFor="email">Почта для писем о заказах</label>
          <input id="email" className="input" type="email" value={email}
                 placeholder="вы@example.com"
                 onChange={(e) => setEmail(e.target.value)}
                 onBlur={() => email !== (user.email ?? '')
                   && save({ email }, 'Почта сохранена')} />
        </div>

        {user.phone && (
          <div className="notice">
            <Icon name="phone" size={15} /> Номер {user.phone} подтверждён
          </div>
        )}
      </div>

      <h2 style={{ marginTop: 40 }}>Уведомления</h2>
      <p className="subtitle" style={{ marginTop: 4 }}>
        Письмо о принятом заказе приходит всегда: в нём реквизиты для оплаты.
      </p>

      <div className="stack" style={{ marginTop: 16 }}>
        <label className="row-between notice" style={{ cursor: 'pointer' }}>
          <span><Icon name="mail" size={16} /> Письма на почту</span>
          <input type="checkbox" checked={user.notify_email}
                 onChange={(e) => save({ notify_email: e.target.checked },
                                        'Сохранено')} />
        </label>

        <label className="row-between notice" style={{ cursor: 'pointer' }}>
          <span><Icon name="send" size={16} /> Сообщения в Telegram</span>
          <input type="checkbox" checked={user.notify_telegram}
                 disabled={!user.tg_linked}
                 onChange={(e) => save({ notify_telegram: e.target.checked },
                                        'Сохранено')} />
        </label>

        {!user.tg_linked && (
          <button className="btn btn-block" disabled={linking} onClick={linkTelegram}>
            <Icon name="send" size={17} /> Привязать Telegram
          </button>
        )}
      </div>

      <h2 style={{ marginTop: 40 }}>Разделы</h2>
      <div className="stack" style={{ marginTop: 16 }}>
        <Link className="btn btn-block row-between" to="/orders">
          <span><Icon name="package" size={17} /> Мои заказы</span>
          <Icon name="chevron-right" size={17} />
        </Link>
        <Link className="btn btn-block row-between" to="/favorites">
          <span><Icon name="heart" size={17} /> Избранное</span>
          <Icon name="chevron-right" size={17} />
        </Link>
        <Link className="btn btn-block row-between" to="/delivery">
          <span><Icon name="truck" size={17} /> Доставка и оплата</span>
          <Icon name="chevron-right" size={17} />
        </Link>
        {cfg?.support && (
          <a className="btn btn-block row-between" href={cfg.support}
             target="_blank" rel="noreferrer">
            <span><Icon name="message-circle" size={17} /> Написать нам</span>
            <Icon name="chevron-right" size={17} />
          </a>
        )}
        {user.is_admin && (
          <button className="btn btn-primary btn-block row-between"
                  onClick={() => navigate('/admin')}>
            <span><Icon name="sliders-horizontal" size={17} /> Управление магазином</span>
            <Icon name="chevron-right" size={17} />
          </button>
        )}
      </div>

      <button className="btn btn-block" style={{ marginTop: 32 }} onClick={signOut}>
        <Icon name="log-out" size={17} /> Выйти
      </button>
      {node}
    </div>
  );
}
