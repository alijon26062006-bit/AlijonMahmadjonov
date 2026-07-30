<?php
declare(strict_types=1);

namespace Controllers;

use Core\Controller;
use Core\Response;
use Models\Movie;
use Models\History;

final class WatchController extends Controller
{
    /**
     * POST /watch — {movie_id}. Registers a view, seeds "continue watching",
     * and returns the playable URL.
     */
    public function store(): void
    {
        $user = $this->authenticate(false); // watching allowed without strict auth
        $movieId = (int) $this->input('movie_id', 0);
        if ($movieId <= 0) {
            Response::error('Missing movie_id', 422);
        }

        $movie = new Movie();
        $data  = $movie->find($movieId);
        if (!$data) {
            Response::error('Movie not found', 404);
        }

        $movie->incrementViews($movieId, $this->userId);
        if ($this->userId) {
            (new History())->record($this->userId, $movieId, 0);
        }

        Response::ok([
            'watch_url' => $data['watch_url'] ?? null,
            'trailer'   => $data['trailer'] ?? null,
            'title'     => $data['title'],
        ]);
    }
}
