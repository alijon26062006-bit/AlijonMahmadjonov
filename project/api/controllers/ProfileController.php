<?php
declare(strict_types=1);

namespace Controllers;

use Core\Controller;
use Core\Response;
use Models\User;

final class ProfileController extends Controller
{
    /** GET /profile — authenticated user's profile + stats. */
    public function show(): void
    {
        $this->authenticate();
        $profile = (new User())->profile($this->userId);
        if (!$profile) {
            Response::error('Profile not found', 404);
        }
        $profile['is_admin'] = $this->isAdmin();
        unset($profile['id']); // don't leak internal id
        Response::ok($profile);
    }

    /**
     * POST /profile — upsert from Telegram initData (touch last_seen).
     * Used by the mini app on launch to register the user.
     */
    public function store(): void
    {
        $this->authenticate();
        $profile = (new User())->profile($this->userId);
        $profile['is_admin'] = $this->isAdmin();
        unset($profile['id']);
        Response::ok($profile);
    }
}
