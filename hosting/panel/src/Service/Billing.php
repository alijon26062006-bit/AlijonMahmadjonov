<?php
declare(strict_types=1);

namespace Hosting\Service;

use Hosting\Database;

/**
 * Баланс клиента и срок его тарифа.
 *
 * Баланс лежит в users.balance_tjs, а каждое движение денег — отдельной строкой
 * в payments. Так баланс всегда можно пересчитать по истории и сверить: если
 * они разошлись, это видно, а не теряется молча.
 *
 * ВАЖНО: приёма денег здесь нет. Пополнение пока делает администратор вручную
 * (после перевода на карту/кошелёк), и это честно написано в интерфейсе.
 * Автоматический приём требует договора с платёжной системой — см. README.
 */
final class Billing
{
    public function __construct(private Database $db)
    {
    }

    /** Сводка для панели: баланс, тариф, сколько дней осталось. */
    public function summary(array $user): array
    {
        $subscription = $this->subscription((int) $user['id']);
        $endsAt = $subscription['current_period_end'] ?? null;

        return [
            'balance'    => (float) ($user['balance_tjs'] ?? 0),
            'ends_at'    => $endsAt,
            'days_left'  => self::daysLeft($endsAt),
            'status'     => $subscription['status'] ?? null,
        ];
    }

    public function subscription(int $userId): ?array
    {
        $stmt = $this->db->pdo()->prepare(
            'SELECT * FROM subscriptions WHERE user_id = ? ORDER BY id DESC LIMIT 1'
        );
        $stmt->execute([$userId]);
        $row = $stmt->fetch();

        return $row === false ? null : $row;
    }

    /**
     * Сколько дней осталось. null — если срок не задан (тариф без срока).
     *
     * Считаем по календарным дням от «сейчас», а не делением секунд: клиент
     * считает так же, и расхождение в один день на границе суток выглядит как
     * ошибка в счёте.
     */
    public static function daysLeft(?string $endsAt): ?int
    {
        if ($endsAt === null || $endsAt === '') {
            return null;
        }
        $end = strtotime($endsAt);
        if ($end === false) {
            return null;
        }

        $diff = (new \DateTimeImmutable('today'))
            ->diff((new \DateTimeImmutable(date('Y-m-d', $end))));

        return $diff->invert === 1 ? -$diff->days : $diff->days;
    }

    /** История движений по счёту. */
    public function payments(int $userId, int $limit = 20): array
    {
        $stmt = $this->db->pdo()->prepare(
            'SELECT * FROM payments WHERE user_id = ? ORDER BY id DESC LIMIT ' . max(1, min(100, $limit))
        );
        $stmt->execute([$userId]);

        return $stmt->fetchAll();
    }

    /**
     * Пополнение счёта. Вызывается администратором после подтверждения перевода.
     *
     * Обе записи — строка в payments и изменение баланса — в одной транзакции:
     * иначе при сбое между ними баланс и история разойдутся, и разобраться, кто
     * кому должен, будет уже нельзя.
     */
    public function credit(int $userId, float $amount, string $comment = '', string $provider = 'manual'): void
    {
        if ($amount <= 0) {
            throw new \InvalidArgumentException('Сумма пополнения должна быть больше нуля');
        }

        $pdo = $this->db->pdo();
        $pdo->beginTransaction();
        try {
            $pdo->prepare(
                'INSERT INTO payments (user_id, provider, amount_tjs, status, external_id, created_at)
                 VALUES (?, ?, ?, \'paid\', ?, ?)'
            )->execute([$userId, $provider, $amount, mb_substr($comment, 0, 190), gmdate('Y-m-d H:i:s')]);

            $pdo->prepare('UPDATE users SET balance_tjs = balance_tjs + ? WHERE id = ?')
                ->execute([$amount, $userId]);

            $pdo->commit();
        } catch (\Throwable $e) {
            $pdo->rollBack();
            throw $e;
        }
    }

    /**
     * Заявки на пополнение, которые ждут подтверждения администратора.
     *
     * @return list<array<string,mixed>>
     */
    public function pendingPayments(int $limit = 50): array
    {
        $stmt = $this->db->pdo()->query(
            'SELECT p.*, u.email, u.display_name, u.system_user
               FROM payments p
               JOIN users u ON u.id = p.user_id
              WHERE p.status = \'pending\'
              ORDER BY p.id ASC
              LIMIT ' . max(1, min(200, $limit))
        );

        return $stmt === false ? [] : $stmt->fetchAll();
    }

    /**
     * Подтверждение заявки: деньги приходят на баланс, заявка становится «оплачена».
     *
     * Возвращает false, если заявки уже нет в статусе pending — так двойное
     * нажатие «Зачислить» не зачислит сумму дважды. Проверка и обновление идут
     * одним UPDATE ... WHERE status = 'pending': между SELECT и UPDATE успел бы
     * вклиниться второй запрос.
     */
    public function approvePayment(int $paymentId): bool
    {
        $pdo = $this->db->pdo();
        $pdo->beginTransaction();
        try {
            $stmt = $pdo->prepare('UPDATE payments SET status = \'paid\' WHERE id = ? AND status = \'pending\'');
            $stmt->execute([$paymentId]);
            if ($stmt->rowCount() === 0) {
                $pdo->rollBack();
                return false;
            }

            $row = $pdo->prepare('SELECT user_id, amount_tjs FROM payments WHERE id = ?');
            $row->execute([$paymentId]);
            $payment = $row->fetch();
            if ($payment === false) {
                $pdo->rollBack();
                return false;
            }

            $pdo->prepare('UPDATE users SET balance_tjs = balance_tjs + ? WHERE id = ?')
                ->execute([$payment['amount_tjs'], $payment['user_id']]);

            $pdo->commit();
            return true;
        } catch (\Throwable $e) {
            $pdo->rollBack();
            throw $e;
        }
    }

    /** Отклонение заявки: баланс не трогаем, заявка остаётся в истории со статусом «отклонена». */
    public function rejectPayment(int $paymentId): bool
    {
        $stmt = $this->db->pdo()->prepare(
            'UPDATE payments SET status = \'failed\' WHERE id = ? AND status = \'pending\''
        );
        $stmt->execute([$paymentId]);

        return $stmt->rowCount() > 0;
    }

    /** Деньги в понятном виде: 25 → «25.00 TJS». */
    public static function money(float $amount): string
    {
        return number_format($amount, 2, '.', ' ') . ' TJS';
    }
}
