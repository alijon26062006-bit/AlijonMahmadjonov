package main

import (
	"context"
	"errors"
	"fmt"

	"github.com/averix/api/internal/config"
	"github.com/averix/api/internal/telegram"
)

// chatTestCmd answers the only question an operator has about this
// integration: does it work, and if not, why.
//
// "The bot does not work" is almost never the bot. It is one of three things,
// and Telegram says which one in plain words — so this command asks it and
// prints the answer instead of a status code.
func chatTestCmd(ctx context.Context, _ []string) error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}

	if !cfg.Telegram.Configured() {
		fmt.Println("Чат сотрудников не настроен.")
		fmt.Println()
		fmt.Println("  В .env нужны две строки:")
		fmt.Println("    TELEGRAM_BOT_TOKEN=   токен от @BotFather")
		fmt.Println("    TELEGRAM_CHAT_ID=     куда писать (см. ниже)")
		fmt.Println()
		printWhereToGetTheChatID()
		return errors.New("нечего проверять, пока не задан бот")
	}

	client := telegram.New(telegram.Config{
		BotToken: cfg.Telegram.BotToken, ChatID: cfg.Telegram.ChatID,
		BaseURL: cfg.Telegram.BaseURL, AppURL: cfg.AppURL,
	})
	if err := client.Check(ctx); err != nil {
		fmt.Println("Сообщение не дошло.")
		fmt.Printf("  %v\n\n", err)
		fmt.Println("  Что это обычно значит:")
		fmt.Println("    chat not found          — id чата неверный, или бота нет в этом чате.")
		fmt.Println("    bot was blocked         — человек заблокировал бота.")
		fmt.Println("    Forbidden: bot can't initiate conversation with a user")
		fmt.Println("                            — вы указали свой личный id, но ни разу не")
		fmt.Println("                              нажимали «Старт» в самом боте. Telegram не")
		fmt.Println("                              разрешает боту писать первым. Откройте бота")
		fmt.Println("                              в Telegram, нажмите «Старт» и повторите.")
		fmt.Println("    Unauthorized            — токен неверный или отозван.")
		fmt.Println()
		printWhereToGetTheChatID()
		return errors.New("чат сотрудников не работает")
	}

	fmt.Println("Сообщение доставлено — посмотрите в чат.")
	fmt.Println("Туда будут приходить уведомления о заявках на проверку личности:")
	fmt.Println("одна строка и ссылка в панель. Документы в чат не отправляются.")
	return nil
}

func printWhereToGetTheChatID() {
	fmt.Println("  Откуда взять TELEGRAM_CHAT_ID:")
	fmt.Println("    · личный чат — ваш собственный числовой id (положительное число).")
	fmt.Println("      Узнать: напишите боту @userinfobot. Перед первым уведомлением")
	fmt.Println("      обязательно откройте своего бота и нажмите «Старт», иначе Telegram")
	fmt.Println("      не даст ему написать вам первым.")
	fmt.Println("    · общий чат — id группы (обычно отрицательное, вида -1001234567890).")
	fmt.Println("      Добавьте бота в группу, напишите там что-нибудь и откройте")
	fmt.Println("      https://api.telegram.org/bot<ТОКЕН>/getUpdates — id будет в \"chat\".")
	fmt.Println()
	fmt.Println("  Это не тот администратор, который управляет площадкой: тот создаётся")
	fmt.Println("  командой averixctl create-admin по адресу почты и с Telegram не связан.")
}
