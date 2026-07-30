<?php
declare(strict_types=1);

namespace Controllers;

use Core\Controller;
use Core\Response;
use Models\Movie;
use Models\Announcement;
use Models\Banner;

final class MovieController extends Controller
{
    /** GET /movies — filtered/paginated list. */
    public function index(): void
    {
        $movie = new Movie();
        $filters = [
            'category'   => $this->query('category'),
            'genre'      => $this->query('genre'),
            'country'    => $this->query('country'),
            'year'       => $this->query('year'),
            'min_rating' => $this->query('min_rating'),
            'type_flag'  => $this->query('flag'),      // new|popular|recommended
            'status'     => $this->query('status', 'published'),
            'sort'       => $this->query('sort', 'newest'),
            'search'     => $this->query('q'),
            'limit'      => $this->query('limit', 20),
            'offset'     => $this->query('offset', 0),
        ];
        $items = $movie->all($filters);
        Response::ok($items, [
            'count'  => count($items),
            'limit'  => (int) $filters['limit'],
            'offset' => (int) $filters['offset'],
        ]);
    }

    /** GET /movie — single movie detail with similar titles. */
    public function show(): void
    {
        $id = (int) $this->query('id', 0);
        if ($id <= 0) {
            Response::error('Missing movie id', 422);
        }
        $movie = new Movie();
        $data  = $movie->find($id);
        if (!$data) {
            Response::error('Movie not found', 404);
        }
        $data['similar'] = $movie->similar($id);
        Response::ok($data);
    }

    /**
     * GET /home — everything the mini app home page needs, in one call:
     * banners + all category rails.
     */
    public function home(): void
    {
        $movie = new Movie();

        $section = static fn (array $f) => (new Movie())->all($f);

        $data = [
            'banners'        => (new Banner())->active(8),
            'announcements'  => (new Announcement())->active(10),
            'new'            => $section(['flag' => 'new', 'sort' => 'newest', 'limit' => 20]),
            'popular'        => $section(['flag' => 'popular', 'sort' => 'popular', 'limit' => 20]),
            'recommended'    => $section(['flag' => 'recommended', 'sort' => 'rating', 'limit' => 20]),
            'coming_soon'    => $section(['status' => 'coming_soon', 'sort' => 'soon', 'limit' => 20]),
            'in_cinema'      => $section(['status' => 'in_cinema', 'sort' => 'rating', 'limit' => 20]),
            'series'         => $section(['category' => 'series', 'limit' => 20]),
            'movies'         => $section(['category' => 'movie', 'limit' => 20]),
            'anime'          => $section(['category' => 'anime', 'limit' => 20]),
            'cartoons'       => $section(['category' => 'cartoon', 'limit' => 20]),
        ];

        // Fallback: if no dedicated banners, surface top announcements as hero
        if (empty($data['banners'])) {
            $data['banners'] = array_map(static function ($a) {
                return [
                    'id'           => $a['id'],
                    'title'        => $a['title'],
                    'subtitle'     => $a['genre'] ?? null,
                    'image'        => $a['backdrop'] ?: $a['poster'],
                    'description'  => $a['description'],
                    'rating'       => $a['rating'],
                    'genre'        => $a['genre'] ?? null,
                    'release_date' => $a['release_date'],
                    'movie_id'     => $a['movie_id'] ?? null,
                ];
            }, $data['announcements']);
        }

        Response::ok($data);
    }
}
