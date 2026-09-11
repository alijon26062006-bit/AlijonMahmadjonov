<?php
declare(strict_types=1);

namespace Hosting\Controller;

use Hosting\Config;
use Hosting\Http\Request;
use Hosting\Http\Response;
use Hosting\Http\UnauthorizedException;
use Hosting\Model\BackupRepository;
use Hosting\Model\DatabaseRepository;
use Hosting\Model\JobRepository;
use Hosting\Model\NotificationRepository;
use Hosting\Model\PlanRepository;
use Hosting\Model\SiteRepository;
use Hosting\Service\Auth;
use Hosting\Service\Quota;
use Hosting\Support\View;

final class DashboardController
{
    public function __construct(
        private Config $config,
        private Auth $auth,
        private \Hosting\Service\Billing $billing,
        private SiteRepository $sites,
        private DatabaseRepository $databases,
        private PlanRepository $plans,
        private JobRepository $jobs,
        private BackupRepository $backups,
        private NotificationRepository $notifications,
        private View $view,
    ) {
    }

    public function index(Request $request): Response
    {
        $user = $this->auth->user();
        if ($user === null) {
            throw new UnauthorizedException();
        }

        $home = rtrim($this->config->str('users_root'), '/') . '/' . $user['system_user'];
        $quota = is_dir($home)
            ? Quota::usage($home, (int) $user['disk_quota_mb'])
            : ['used' => 0, 'limit' => (int) $user['disk_quota_mb'] * 1024 * 1024, 'percent' => 0, 'exceeded' => false];

        return Response::html($this->view->page('dashboard', [
            'user'          => $user,
            'plan'          => $this->plans->findById((int) $user['plan_id']),
            'quota'         => $quota,
            'sites'         => $this->sites->forUser((int) $user['id']),
            'databases'     => $this->databases->forUser((int) $user['id']),
            'recentJobs'    => $this->jobs->recentForUser((int) $user['id'], 10),
            'lastBackup'    => $this->backups->latestSuccessful((int) $user['id']),
            'notifications' => $this->notifications->forUser((int) $user['id'], 5),
            'summary'       => $this->billing->summary($user),
            'databaseCount' => count($this->databases->forUser((int) $user['id'])),
        ]));
    }
}
