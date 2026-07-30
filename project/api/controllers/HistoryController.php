<?php
namespace Controllers;

use Core\Controller;
use Core\Response;
use Models\History;

final class HistoryController extends Controller
{
    /** GET /history — continue watching. */
    public function index(): void
    {
        $this->authenticate();
        Response::ok((new History())->recent($this->userId));
    }

    /** POST /history — record {movie_id, progress}. */
    public function store(): void
    {
        $this->authenticate();
        $movieId  = (int) $this->input('movie_id', 0);
        $progress = (int) $this->input('progress', 0);
        if ($movieId <= 0) {
            Response::error('Missing movie_id', 422);
        }
        (new History())->record($this->userId, $movieId, $progress);
        Response::ok(['recorded' => true]);
    }
}
