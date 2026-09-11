<?php
declare(strict_types=1);

namespace Hosting\Controller;

use Hosting\Database;
use Hosting\Http\ForbiddenException;
use Hosting\Http\Request;
use Hosting\Http\Response;
use Hosting\Http\UnauthorizedException;
use Hosting\Model\JobRepository;
use Hosting\Model\SiteRepository;
use Hosting\Model\UserRepository;
use Hosting\Service\Auth;
use Hosting\Service\Billing;
use Hosting\Support\Flash;
use Hosting\Support\View;

/** Админ-панель: список клиентов, статус сайтов, журнал действий. Доступ только role=admin. */
final class AdminController
{
    public function __construct(
        private Database $db,
        private Auth $auth,
        private Billing $billing,
        private UserRepository $users,
        private SiteRepository $sites,
        private JobRepository $jobs,
        private View $view,
    ) {
    }

    public function index(Request $request): Response
    {
        $this->requireAdmin();

        return Response::html($this->view->page('admin/index', [
            'csrf'        => $this->auth->csrfToken(),
            'users'       => $this->users->all(),
            'sites'       => $this->sites->allActive(),
            'auditLog'    => $this->db->recentAuditLog(50),
            'pendingJobs' => $this->jobs->countPending(),
            'requests'    => $this->billing->pendingPayments(),
        ]));
    }

    public function suspendUser(Request $request, int $id): Response
    {
        $this->requireAdmin();
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return Response::redirect('/admin');
        }
        $target = $this->users->findById($id);
        if ($target !== null) {
            $this->users->setStatus($id, 'suspended');
            foreach ($this->sites->forUser($id) as $site) {
                $this->jobs->enqueue('suspend_site', $id, (int) $site['id'], ['site_id' => $site['id']]);
            }
            $this->db->log((int) $this->auth->user()['id'], 'admin.user_suspended', 'user', $id);
            Flash::add('success', 'Клиент приостановлен, его сайты приостанавливаются');
        }
        return Response::redirect('/admin');
    }

    public function activateUser(Request $request, int $id): Response
    {
        $this->requireAdmin();
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return Response::redirect('/admin');
        }
        $target = $this->users->findById($id);
        if ($target !== null) {
            $this->users->setStatus($id, 'active');
            foreach ($this->sites->forUser($id) as $site) {
                if ($site['status'] === 'suspended') {
                    $this->jobs->enqueue('unsuspend_site', $id, (int) $site['id'], ['site_id' => $site['id']]);
                }
            }
            $this->db->log((int) $this->auth->user()['id'], 'admin.user_activated', 'user', $id);
            Flash::add('success', 'Клиент возобновлён');
        }
        return Response::redirect('/admin');
    }

    /**
     * Подтверждение заявки на пополнение: деньги зачисляются на баланс клиента.
     *
     * Это единственное место, где баланс растёт. Владелец хостинга нажимает
     * кнопку после того, как увидел перевод на карте — автоматического приёма
     * платежей у панели нет, и выдумывать его здесь было бы обманом.
     */
    public function approvePayment(Request $request, int $id): Response
    {
        $admin = $this->requireAdmin();
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return Response::redirect('/admin');
        }

        if ($this->billing->approvePayment($id)) {
            $this->db->log((int) $admin['id'], 'admin.payment_approved', 'payment', $id);
            Flash::add('success', 'Заявка подтверждена, баланс пополнен');
        } else {
            // Обычно это второе нажатие на ту же кнопку — успокаиваем, а не пугаем.
            Flash::add('error', 'Заявка уже обработана');
        }

        return Response::redirect('/admin');
    }

    public function rejectPayment(Request $request, int $id): Response
    {
        $admin = $this->requireAdmin();
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return Response::redirect('/admin');
        }

        if ($this->billing->rejectPayment($id)) {
            $this->db->log((int) $admin['id'], 'admin.payment_rejected', 'payment', $id);
            Flash::add('success', 'Заявка отклонена');
        } else {
            Flash::add('error', 'Заявка уже обработана');
        }

        return Response::redirect('/admin');
    }

    /** Ручное пополнение без заявки — например, когда клиент заплатил наличными. */
    public function creditUser(Request $request, int $id): Response
    {
        $admin = $this->requireAdmin();
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return Response::redirect('/admin');
        }

        $target = $this->users->findById($id);
        if ($target === null) {
            Flash::add('error', 'Клиент не найден');
            return Response::redirect('/admin');
        }

        $amount = (float) str_replace(',', '.', trim($request->input('amount')));
        if ($amount <= 0 || $amount > 100000) {
            Flash::add('error', 'Сумма должна быть от 0.01 до 100000 TJS');
            return Response::redirect('/admin');
        }

        $this->billing->credit($id, $amount, trim($request->input('comment')) ?: 'вручную');
        $this->db->log((int) $admin['id'], 'admin.balance_credited', 'user', $id);
        Flash::add('success', 'Баланс клиента пополнен на ' . Billing::money($amount));

        return Response::redirect('/admin');
    }

    private function requireAdmin(): array
    {
        $user = $this->auth->user();
        if ($user === null) {
            throw new UnauthorizedException();
        }
        if ($user['role'] !== 'admin') {
            throw new ForbiddenException('Только для администраторов');
        }
        return $user;
    }
}
