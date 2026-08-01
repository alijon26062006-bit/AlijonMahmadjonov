<?php

namespace CargoBot\Handler\User;

use CargoBot\Bot;
use CargoBot\Texts;

class StartHandler
{
    private Bot $bot;

    public function __construct(Bot $bot)
    {
        $this->bot = $bot;
    }

    public function start(): void
    {
        $welcome = $this->bot->settings->get('welcome_text', '👋 Добро пожаловать!');
        $this->bot->send((string) $welcome, Texts::mainMenu($this->bot->lang));
    }

    public function fallback(): void
    {
        $this->bot->send(
            'Выберите действие в меню ниже 👇',
            Texts::mainMenu($this->bot->lang)
        );
    }
}
