package notifications

import (
	"context"
	"fmt"
	"strings"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/logx"
)

// Realtime is the live channel: the same socket that carries chat.
type Realtime interface {
	PublishRaw(ctx context.Context, recipients []uuid.UUID, payload any)
	Online(userID uuid.UUID) bool
}

// Service composes notifications and hands them to the store. It implements
// every module's Notifier interface, so the modules keep their narrow view
// (proposals knows "a proposal was received", not what an email looks like)
// and the phrasing lives here, in one language.
type Service struct {
	store    *Store
	mailer   *Mailer
	realtime Realtime
	push     bool
}

func NewService(store *Store, mailer *Mailer, realtime Realtime, pushConfigured bool) *Service {
	return &Service{store: store, mailer: mailer, realtime: realtime, push: pushConfigured}
}

// Notify records one notification and pushes it to the open socket. Failures
// are logged and swallowed: a notification that could not be written must
// never fail the action that caused it.
func (s *Service) Notify(ctx context.Context, in Input) {
	online := s.realtime != nil && s.realtime.Online(in.UserID)
	id, err := s.store.Create(ctx, in, online)
	if err != nil {
		logx.From(ctx).Error("notifications: could not record", "type", in.Type, "error", err)
		return
	}
	if s.realtime != nil {
		unread, _ := s.store.UnreadCount(ctx, in.UserID)
		s.realtime.PublishRaw(ctx, []uuid.UUID{in.UserID}, map[string]any{
			"type": "notification",
			"notification": map[string]any{
				"id": id, "type": in.Type, "title": in.Title, "body": in.Body,
				"href": in.Href, "priority": in.Priority,
			},
			"unread_count": unread,
		})
	}
}

// ── Reading ─────────────────────────────────────────────────────────────────

func (s *Service) Store() *Store { return s.store }

// ── What the modules call ───────────────────────────────────────────────────

// proposals.Notifier

func (s *Service) ProposalReceived(ctx context.Context, clientID, projectID, proposalID uuid.UUID, developerName string) {
	title := s.store.projectTitle(ctx, projectID)
	s.Notify(ctx, Input{
		UserID: clientID, Type: TypeProposalReceived,
		Title:     "Новый отклик на «" + title + "»",
		Body:      developerName + " предлагает выполнить ваш проект. Посмотрите условия и портфолио.",
		Href:      "/projects/" + s.store.projectSlug(ctx, projectID) + "/proposals",
		ProjectID: &projectID, ProposalID: &proposalID,
	})
}

func (s *Service) ProposalShortlisted(ctx context.Context, developerID, projectID, proposalID uuid.UUID) {
	title := s.store.projectTitle(ctx, projectID)
	s.Notify(ctx, Input{
		UserID: developerID, Type: TypeProposalShortlisted,
		Title:     "Ваш отклик в шорт-листе",
		Body:      "Заказчик выделил ваш отклик на «" + title + "» среди остальных. Обычно за этим следует разговор.",
		Href:      "/projects/" + s.store.projectSlug(ctx, projectID),
		ProjectID: &projectID, ProposalID: &proposalID,
	})
}

func (s *Service) ProposalDeclined(ctx context.Context, developerID, projectID, proposalID uuid.UUID, reason string) {
	title := s.store.projectTitle(ctx, projectID)
	body := "Заказчик выбрал другой вариант для «" + title + "». Это не оценка вашей работы — так бывает."
	if strings.TrimSpace(reason) != "" {
		body += "\n\nПричина: " + strings.TrimSpace(reason)
	}
	s.Notify(ctx, Input{
		UserID: developerID, Type: TypeProposalDeclined,
		Title: "Отклик не принят", Body: body,
		Href: "/proposals", ProjectID: &projectID, ProposalID: &proposalID,
	})
}

// contracts.Notifier

func (s *Service) ContractSigned(ctx context.Context, contractID, developerID uuid.UUID) {
	title := s.store.contractTitle(ctx, contractID)
	s.Notify(ctx, Input{
		UserID: developerID, Type: TypeContractStarted, Priority: "high",
		Title: "Контракт подписан: «" + title + "»",
		Body:  "Заказчик принял ваш отклик. Откройте рабочее пространство — там этапы, сроки и переписка.",
		Href:  "/contracts/" + contractID.String(), ContractID: &contractID,
	})
}

func (s *Service) MilestoneChanged(ctx context.Context, contractID, milestoneID, recipientID uuid.UUID, status string) {
	milestone := s.store.milestoneTitle(ctx, milestoneID)
	contract := s.store.contractTitle(ctx, contractID)
	href := "/contracts/" + contractID.String()
	base := Input{UserID: recipientID, Href: href, ContractID: &contractID, MilestoneID: &milestoneID}

	switch status {
	case "funded":
		base.Type, base.Priority = TypePaymentSucceeded, "high"
		base.Title = "Этап оплачен: «" + milestone + "»"
		base.Body = "Заказчик внёс оплату по контракту «" + contract + "». Можно начинать работу — деньги удерживаются до приёмки."
	case "submitted":
		base.Type, base.Priority = TypeMilestoneSubmitted, "high"
		base.Title = "Этап сдан на проверку: «" + milestone + "»"
		base.Body = "Исполнитель считает этап по контракту «" + contract + "» готовым. Проверьте результат и примите его или запросите правки."
	case "revision_requested":
		base.Type, base.Priority = TypeMilestoneRevision, "high"
		base.Title = "Запрошены правки: «" + milestone + "»"
		base.Body = "Заказчик посмотрел результат по «" + contract + "» и просит доработать. Подробности — в рабочем пространстве."
	case "approved":
		base.Type, base.Priority = TypeMilestoneApproved, "high"
		base.Title = "Этап принят: «" + milestone + "»"
		base.Body = "Заказчик принял результат по контракту «" + contract + "». Выплата будет переведена после подтверждения."
	case "released":
		base.Type, base.Priority = TypeMilestoneReleased, "high"
		base.Title = "Выплата переведена: «" + milestone + "»"
		base.Body = "Оплата этапа по контракту «" + contract + "» переведена вам. Сумма отражена в разделе «Доходы»."
	case "disputed":
		base.Type, base.Priority = TypeDisputeOpened, "high"
		base.Title = "Открыт спор по этапу «" + milestone + "»"
		base.Body = "По контракту «" + contract + "» открыт спор. Администратор рассмотрит обе позиции; переписка в рабочем пространстве остаётся доступной."
	case "cancelled":
		base.Type = TypeContractCancelled
		base.Title = "Этап отменён: «" + milestone + "»"
		base.Body = "Этап по контракту «" + contract + "» отменён. Если он был оплачен, средства вернутся заказчику."
	default:
		// Starting work is the developer's own action; the other side sees it
		// in the thread as a system message, and does not need a bell for it.
		return
	}
	s.Notify(ctx, base)
}

// messaging.Notifier

func (s *Service) MessageReceived(ctx context.Context, conversationID, messageID, recipientID uuid.UUID,
	senderName, preview string) {

	preview = strings.TrimSpace(preview)
	if len([]rune(preview)) > 140 {
		preview = string([]rune(preview)[:140]) + "…"
	}
	s.Notify(ctx, Input{
		UserID: recipientID, Type: TypeMessageReceived,
		Title: "Сообщение от " + senderName, Body: preview,
		Href:     "/messages/" + conversationID.String(),
		Metadata: map[string]any{"conversation_id": conversationID, "message_id": messageID},
	})
}

// payments.Notifier

func (s *Service) PaymentConfirmed(ctx context.Context, recipientID, contractID uuid.UUID,
	amountMinor int64, currency, kind string) {

	contract := s.store.contractTitle(ctx, contractID)
	amount := FormatMoney(amountMinor, currency)
	in := Input{UserID: recipientID, Href: "/contracts/" + contractID.String(), ContractID: &contractID,
		Priority: "high", Metadata: map[string]any{"amount_minor": amountMinor, "currency": currency, "kind": kind}}
	// The kinds are what the payments module says happened: "funded" goes to
	// both parties when a charge is confirmed, "paid" to the freelancer when
	// a payout is confirmed, "refund" to the client when money comes back.
	switch kind {
	case "paid", "payout":
		in.Type = TypeMilestoneReleased
		in.Title = "Выплата " + amount + " переведена"
		in.Body = "Администратор подтвердил перевод по контракту «" + contract + "». Сумма указана за вычетом комиссии платформы."
		in.Href = "/earnings"
	case "refund", "refunded":
		in.Type = TypePaymentRefunded
		in.Title = "Возврат " + amount
		in.Body = "Средства по контракту «" + contract + "» возвращены."
	case "failed":
		in.Type = TypePaymentFailed
		in.Title = "Платёж " + amount + " не прошёл"
		in.Body = "Оплата по контракту «" + contract + "» не подтверждена. Проверьте реквизиты и попробуйте снова."
	default:
		in.Type = TypePaymentSucceeded
		in.Title = "Платёж " + amount + " подтверждён"
		in.Body = "Оплата по контракту «" + contract + "» получена и удерживается до приёмки этапа."
	}
	s.Notify(ctx, in)
}

// githubint.Notifier

func (s *Service) GitHubAnalysisComplete(ctx context.Context, userID uuid.UUID, technologies int) {
	body := "Мы проанализировали ваши репозитории."
	if technologies > 0 {
		body = fmt.Sprintf("Мы проанализировали ваши репозитории и подтвердили %s. Они отмечены в профиле как проверенные.",
			plural(technologies, "технологию", "технологии", "технологий"))
	}
	s.Notify(ctx, Input{UserID: userID, Type: TypeGitHubComplete, Title: "Анализ GitHub завершён",
		Body: body, Href: "/profile"})
}

func (s *Service) GitHubAnalysisFailed(ctx context.Context, userID uuid.UUID, reason string) {
	s.Notify(ctx, Input{UserID: userID, Type: TypeGitHubFailed, Title: "Анализ GitHub не удался",
		Body: "Не получилось прочитать ваши репозитории: " + reason + ". Попробуйте переподключить GitHub.",
		Href: "/settings/github"})
}

// reviews

func (s *Service) ContractCompleted(ctx context.Context, userID, contractID uuid.UUID) {
	title := s.store.contractTitle(ctx, contractID)
	s.Notify(ctx, Input{UserID: userID, Type: TypeContractCompleted, Priority: "high", ContractID: &contractID,
		Title: "Контракт завершён: «" + title + "»",
		Body:  "Все этапы приняты и оплачены. Оставьте отзыв о второй стороне — окно открыто 14 дней, и отзывы публикуются одновременно.",
		Href:  "/contracts/" + contractID.String() + "#review"})
}

func (s *Service) ReviewReceived(ctx context.Context, subjectID, authorID, contractID uuid.UUID) {
	author := s.store.userName(ctx, authorID)
	s.Notify(ctx, Input{UserID: subjectID, Type: TypeReviewReceived, ActorID: &authorID, ContractID: &contractID,
		Title: author + " оставил(а) вам отзыв",
		Body:  "Отзыв станет виден после того, как вы оставите свой, или через 14 дней. Так ни один отзыв не пишется в ответ на уже увиденный.",
		Href:  "/contracts/" + contractID.String() + "#review"})
}

func (s *Service) ReviewPublished(ctx context.Context, userID, contractID uuid.UUID) {
	s.Notify(ctx, Input{UserID: userID, Type: TypeReviewPublished, ContractID: &contractID,
		Title: "Отзывы по контракту опубликованы",
		Body:  "Обе стороны оставили отзывы, и теперь они видны в профилях.",
		Href:  "/contracts/" + contractID.String() + "#review"})
}

// account and moderation

func (s *Service) AccountSuspended(ctx context.Context, userID uuid.UUID, reason string) {
	s.Notify(ctx, Input{UserID: userID, Type: TypeAccountSuspended, Priority: "high",
		Title: "Ваш аккаунт заблокирован",
		Body:  "Причина: " + reason + ". Если вы считаете, что это ошибка, ответьте на это письмо.",
	})
}

func (s *Service) AccountWarning(ctx context.Context, userID uuid.UUID, reason string) {
	s.Notify(ctx, Input{UserID: userID, Type: TypeAccountWarning, Priority: "high",
		Title: "Предупреждение от модерации", Body: reason, Href: "/settings"})
}

func (s *Service) DisputeResolved(ctx context.Context, userID, contractID uuid.UUID, outcome string) {
	s.Notify(ctx, Input{UserID: userID, Type: TypeDisputeResolved, Priority: "high", ContractID: &contractID,
		Title: "Спор решён", Body: outcome, Href: "/contracts/" + contractID.String()})
}

// ── Delivery worker ─────────────────────────────────────────────────────────

// DeliverPending sends what is queued. Scheduled by the worker; safe to run
// from more than one process because claiming is a locked update.
func (s *Service) DeliverPending(ctx context.Context) (string, error) {
	batch, err := s.store.claimPending(ctx, 50)
	if err != nil {
		return "", fmt.Errorf("claim deliveries: %w", err)
	}
	if len(batch) == 0 {
		return "", nil
	}

	sent, failed, skipped := 0, 0, 0
	for _, d := range batch {
		switch d.Channel {
		case ChannelEmail:
			if s.mailer == nil || !s.mailer.Configured() {
				_ = s.store.finishDelivery(ctx, d.ID, DeliverySkipped, "", "smtp_not_configured")
				skipped++
				continue
			}
			err := s.mailer.SendNotification(ctx, d.UserID, d.Email, d.FullName, d.Type, d.Title, d.Body, d.Href)
			if err != nil {
				status := DeliveryFailed
				if d.Attempts >= 5 {
					status = DeliverySkipped
				}
				_ = s.store.finishDelivery(ctx, d.ID, status, "", err.Error())
				failed++
				continue
			}
			_ = s.store.finishDelivery(ctx, d.ID, DeliverySent, "", "")
			sent++
		case ChannelPush:
			// The subscription exists and the person asked for push. Sending
			// needs a VAPID key pair; until one is configured this is recorded
			// as skipped with the reason, never as sent.
			_ = s.store.finishDelivery(ctx, d.ID, DeliverySkipped, "", "push_not_configured")
			skipped++
		default:
			_ = s.store.finishDelivery(ctx, d.ID, DeliverySkipped, "", "unknown channel")
			skipped++
		}
	}
	return fmt.Sprintf("deliveries: %d sent, %d failed, %d skipped", sent, failed, skipped), nil
}

// ── Formatting ──────────────────────────────────────────────────────────────

// FormatMoney renders minor units the way a person reads them: thousands
// separated by a thin space, the currency's own sign after the number.
func FormatMoney(minor int64, currency string) string {
	negative := minor < 0
	if negative {
		minor = -minor
	}
	whole := minor / 100
	cents := minor % 100

	digits := fmt.Sprintf("%d", whole)
	var grouped strings.Builder
	for i, r := range digits {
		if i > 0 && (len(digits)-i)%3 == 0 {
			grouped.WriteString(" ")
		}
		grouped.WriteRune(r)
	}
	amount := grouped.String()
	if cents != 0 {
		amount += fmt.Sprintf(",%02d", cents)
	}
	if negative {
		amount = "−" + amount
	}
	switch strings.ToUpper(currency) {
	case "RUB":
		return amount + " ₽"
	case "USD":
		return "$" + amount
	case "EUR":
		return amount + " €"
	case "UZS":
		return amount + " сум"
	case "KZT":
		return amount + " ₸"
	case "UAH":
		return amount + " ₴"
	default:
		return amount + " " + strings.ToUpper(currency)
	}
}

func plural(n int, one, few, many string) string {
	form := many
	switch {
	case n%10 == 1 && n%100 != 11:
		form = one
	case n%10 >= 2 && n%10 <= 4 && (n%100 < 10 || n%100 >= 20):
		form = few
	}
	return fmt.Sprintf("%d %s", n, form)
}
