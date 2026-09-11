<?php
declare(strict_types=1);

namespace Hosting\Controller;

use Hosting\Config;
use Hosting\Database;
use Hosting\Http\Request;
use Hosting\Http\Response;
use Hosting\Http\UnauthorizedException;
use Hosting\Service\Auth;
use Hosting\Service\Billing;
use Hosting\Support\Flash;
use Hosting\Support\View;

/**
 * Баланс и пополнение.
 *
 * Автоматического приёма денег здесь нет и не притворяется, что есть: кнопка
 * оформляет ЗАЯВКУ на пополнение, администратор подтверждает перевод и
 * зачисляет сумму. Нарисовать кнопку «оплатить картой», за которой ничего нет,
 * означало бы обмануть клиента, который уже отправил деньги.
 */
final class BillingController
{
    public function __construct(
        private Config $config,
        private Database $db,
        private Auth $auth,
        private Billing $billing,
        private View $view,
    ) {
    }

    public function index(Request $request): Response
    {
        $user = $this->requireUser();

        return Response::html($this->view->page('billing/index', [
            'csrf'     => $this->auth->csrfToken(),
            'user'     => $user,
            'summary'  => $this->billing->summary($user),
            'payments' => $this->billing->payments((int) $user['id']),
            'details'  => $this->config->str('payment_details'),
        ]));
    }

    /** Заявка на пополнение: клиент сообщает сумму, админ подтверждает перевод. */
    public function requestTopUp(Request $request): Response
    {
        $user = $this->requireUser();
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела');
            return Response::redirect('/billing');
        }

        $amount = (float) str_replace(',', '.', $request->input('amount'));
        if ($amount <= 0 || $amount > 100000) {
            Flash::add('error', 'Укажите сумму от 1 до 100 000 TJS');
            return Response::redirect('/billing');
        }

        // Строка в payments со статусом pending — это заявка, а не деньги:
        // баланс она не меняет, пока администратор не подтвердит перевод.
        $this->db->pdo()->prepare(
            'INSERT INTO payments (user_id, provider, amount_tjs, status, external_id, created_at)
             VALUES (?, \'manual\', ?, \'pending\', ?, ?)'
        )->execute([
            $user['id'],
            $amount,
            'заявка от клиента',
            gmdate('Y-m-d H:i:s'),
        ]);

        $this->db->log((int) $user['id'], 'billing.topup_requested', 'user', (int) $user['id'], 'success', [
            'amount' => $amount,
        ]);
        Flash::add('success', 'Заявка на ' . Billing::money($amount) . ' создана. Переведите сумму по реквизитам ниже и напишите в поддержку — баланс пополнят.');

        return Response::redirect('/billing');
    }

    private function requireUser(): array
    {
        $user = $this->auth->user();
        if ($user === null) {
            throw new UnauthorizedException();
        }
        return $user;
    }
}
