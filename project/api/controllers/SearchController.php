<?php
declare(strict_types=1);

namespace Controllers;

use Core\Controller;
use Core\Response;
use Models\Movie;

final class SearchController extends Controller
{
    /** GET /search — live search with filters. */
    public function index(): void
    {
        $q = trim((string) $this->query('q', ''));

        $filters = [
            'search'     => $q !== '' ? $q : null,
            'category'   => $this->query('category'),
            'genre'      => $this->query('genre'),
            'country'    => $this->query('country'),
            'year'       => $this->query('year'),
            'min_rating' => $this->query('min_rating'),
            'sort'       => $this->query('sort', 'rating'),
            'limit'      => $this->query('limit', 30),
            'offset'     => $this->query('offset', 0),
        ];

        $items = (new Movie())->all($filters);
        Response::ok($items, ['query' => $q, 'count' => count($items)]);
    }
}
