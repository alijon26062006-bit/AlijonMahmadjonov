/** Доставка и оплата — страница, без которой магазину не верят. */
import type { ShopConfig } from '../api/types';
import { fmtPrice } from '../api/client';
import { Icon } from '../components/icons';

export default function DeliveryPage({ cfg }: { cfg?: ShopConfig }) {
  const d = cfg?.delivery;
  return (
    <div className="page fade-in" style={{ maxWidth: 720 }}>
      <h1>Доставка и оплата</h1>

      <h2 style={{ marginTop: 32 }}>Как получить заказ</h2>
      <div className="stack" style={{ marginTop: 16 }}>
        <div className="notice">
          <b><Icon name="truck" size={15} /> Курьером по городу</b>
          <div style={{ marginTop: 4 }}>
            {d ? fmtPrice(d.city_price) : '—'}, в день подтверждения или на следующий.
          </div>
        </div>
        <div className="notice">
          <b><Icon name="package" size={15} /> Почтой по Казахстану</b>
          <div style={{ marginTop: 4 }}>
            {d ? fmtPrice(d.country_price) : '—'}, срок зависит от города —
            он показан при оформлении.
          </div>
        </div>
        {d?.pickup_address && (
          <div className="notice">
            <b><Icon name="store" size={15} /> Самовывоз</b>
            <div style={{ marginTop: 4 }}>Бесплатно: {d.pickup_address}</div>
          </div>
        )}
        {d && d.free_from > 0 && (
          <div className="notice">
            Доставка бесплатна при заказе от {fmtPrice(d.free_from)}.
          </div>
        )}
      </div>

      <h2 style={{ marginTop: 40 }}>Оплата</h2>
      <p className="subtitle" style={{ marginTop: 8 }}>
        Переводом на Kaspi после того, как мы подтвердим заказ и наличие
        вещей. Реквизиты придут сообщением и письмом, номер заказа нужно
        указать в комментарии к переводу.
      </p>

      <h2 style={{ marginTop: 40 }}>Возврат</h2>
      <p className="subtitle" style={{ marginTop: 8 }}>
        Если вещь не подошла по размеру, напишите нам в течение двух дней
        после получения — обменяем или вернём деньги.
      </p>
    </div>
  );
}
