<?php
declare(strict_types=1);

namespace Controllers;

use Core\Controller;
use Core\Response;
use Models\Episode;

final class EpisodeController extends Controller
{
    /** GET /episodes?movie_id= — seasons with their episodes. */
    public function index(): void
    {
        $movieId = (int) $this->query('movie_id', 0);
        if ($movieId <= 0) {
            Response::error('Missing movie_id', 422);
        }
        Response::ok((new Episode())->forMovie($movieId));
    }
}
