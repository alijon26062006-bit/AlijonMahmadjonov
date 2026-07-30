<?php
namespace Controllers;

use Core\Controller;
use Core\Response;
use Models\Announcement;

final class AnnouncementController extends Controller
{
    /** GET /announcements */
    public function index(): void
    {
        $limit = (int) $this->query('limit', 10);
        Response::ok((new Announcement())->active($limit));
    }

    /** GET /announcement?id= */
    public function show(): void
    {
        $id = (int) $this->query('id', 0);
        $item = (new Announcement())->find($id);
        if (!$item) {
            Response::error('Announcement not found', 404);
        }
        Response::ok($item);
    }
}
