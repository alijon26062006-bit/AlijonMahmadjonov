<?php
declare(strict_types=1);

namespace Controllers;

use Core\Controller;
use Core\Response;
use Models\Favorite;
use Models\Movie;

final class FavoriteController extends Controller
{
    /** GET /favorites — the authenticated user's favorites. */
    public function index(): void
    {
        $this->authenticate();
        $ids = (new Favorite())->idsFor($this->userId);
        if (!$ids) {
            Response::ok([]);
        }
        // Fetch each favorited movie (kept simple; lists are small per user)
        $movieModel = new Movie();
        $items = [];
        foreach ($ids as $id) {
            $m = $movieModel->find($id);
            if ($m) {
                $items[] = $m;
            }
        }
        Response::ok($items);
    }

    /** POST /favorites — toggle {movie_id}. */
    public function toggle(): void
    {
        $this->authenticate();
        $movieId = (int) $this->input('movie_id', 0);
        if ($movieId <= 0) {
            Response::error('Missing movie_id', 422);
        }
        $favorited = (new Favorite())->toggle($this->userId, $movieId);
        Response::ok(['favorited' => $favorited]);
    }
}
