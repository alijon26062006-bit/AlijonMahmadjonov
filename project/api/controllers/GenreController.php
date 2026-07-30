<?php
namespace Controllers;

use Core\Controller;
use Core\Response;
use Models\Genre;

final class GenreController extends Controller
{
    /** GET /genres */
    public function index(): void
    {
        Response::ok((new Genre())->all());
    }
}
