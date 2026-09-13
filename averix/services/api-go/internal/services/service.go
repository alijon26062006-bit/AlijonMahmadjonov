package services

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/google/uuid"

	"github.com/averix/api/internal/audit"
	"github.com/averix/api/internal/contracts"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/validate"
	"github.com/averix/api/internal/projects"
	"github.com/averix/api/internal/security"
	"github.com/averix/api/internal/taxonomy"
)

type Settings interface {
	Int(ctx context.Context, key string, fallback int) int
}

// Moderator receives content that needs a human look.
type Moderator interface {
	Flag(ctx context.Context, subjectType string, subjectID uuid.UUID, reason string)
}

// Svc is the service layer. Named Svc because Service is the model.
type Svc struct {
	store     *Store
	taxonomy  *taxonomy.Store
	contracts *contracts.Service
	projects  *projects.Store
	settings  Settings
	moderator Moderator
	audit     *audit.Recorder
}

func NewSvc(store *Store, tax *taxonomy.Store, contractsSvc *contracts.Service,
	projectStore *projects.Store, settings Settings, moderator Moderator, rec *audit.Recorder) *Svc {
	return &Svc{store: store, taxonomy: tax, contracts: contractsSvc, projects: projectStore,
		settings: settings, moderator: moderator, audit: rec}
}

func (s *Svc) Store() *Store { return s.store }

// ── Editing ─────────────────────────────────────────────────────────────────

func (s *Svc) Create(ctx context.Context, id *security.Identity, in UpsertRequest) (*Service, error) {
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return nil, httpx.Forbiddenf("only a freelancer can offer a service")
	}
	limit := 20
	if s.settings != nil {
		limit = s.settings.Int(ctx, "services.max_per_developer", 20)
	}
	n, err := s.store.CountActive(ctx, id.UserID)
	if err != nil {
		return nil, httpx.Internalf(err, "count services")
	}
	if n >= limit {
		e := *httpx.ErrConflict
		e.Code = "service_limit_reached"
		e.Message = fmt.Sprintf("У вас уже %d услуг. Заархивируйте неактуальные, чтобы добавить новую.", n)
		return nil, &e
	}

	validated, err := s.validate(ctx, id.UserID, in)
	if err != nil {
		return nil, err
	}
	serviceID, err := s.store.Create(ctx, *validated)
	if err != nil {
		return nil, httpx.Internalf(err, "create service")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: "service.create", SubjectType: "service", SubjectID: &serviceID})
	s.flagIfNeeded(ctx, serviceID, in)
	return s.View(ctx, id, serviceID)
}

func (s *Svc) Update(ctx context.Context, id *security.Identity, serviceID uuid.UUID, in UpsertRequest) (*Service, error) {
	if err := s.requireOwner(ctx, id, serviceID); err != nil {
		return nil, err
	}
	validated, err := s.validate(ctx, id.UserID, in)
	if err != nil {
		return nil, err
	}
	err = s.store.Update(ctx, serviceID, *validated)
	switch {
	case errors.Is(err, ErrNotFound):
		return nil, httpx.NotFoundf("service %s does not exist", serviceID)
	case err != nil:
		return nil, httpx.Internalf(err, "update service")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: "service.update", SubjectType: "service", SubjectID: &serviceID})
	s.flagIfNeeded(ctx, serviceID, in)
	return s.View(ctx, id, serviceID)
}

var statusTransitions = map[string][]string{
	StatusDraft:    {StatusActive, StatusArchived},
	StatusActive:   {StatusPaused, StatusArchived},
	StatusPaused:   {StatusActive, StatusArchived},
	StatusArchived: {},
}

func (s *Svc) SetStatus(ctx context.Context, id *security.Identity, serviceID uuid.UUID, to string) (*Service, error) {
	if err := s.requireOwner(ctx, id, serviceID); err != nil {
		return nil, err
	}
	_, current, err := s.store.OwnerOf(ctx, serviceID)
	if err != nil {
		return nil, httpx.NotFoundf("service %s does not exist", serviceID)
	}
	allowed := false
	for _, next := range statusTransitions[current] {
		if next == to {
			allowed = true
		}
	}
	if !allowed {
		e := *httpx.ErrConflict
		e.Code = "service_status_conflict"
		e.Message = fmt.Sprintf("Услугу в состоянии «%s» нельзя перевести в «%s».", statusLabel(current), statusLabel(to))
		return nil, &e
	}
	if to == StatusActive {
		// Publishing is where the full standard applies; a draft may have
		// been saved with a single tier and no skills.
		current, err := s.store.ByID(ctx, serviceID)
		if err != nil {
			return nil, httpx.Internalf(err, "load service")
		}
		if problems := publishProblems(current); len(problems) > 0 {
			return nil, httpx.Validation(problems)
		}
	}
	err = s.store.SetStatus(ctx, serviceID, id.UserID, to)
	switch {
	case errors.Is(err, ErrNotFound):
		e := *httpx.ErrConflict
		e.Code = "service_on_moderation"
		e.Message = "Эта услуга отклонена модерацией и не может быть опубликована. Исправьте её или обратитесь в поддержку."
		return nil, &e
	case err != nil:
		return nil, httpx.Internalf(err, "change service status")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: "service." + to, SubjectType: "service", SubjectID: &serviceID})
	return s.View(ctx, id, serviceID)
}

func statusLabel(status string) string {
	switch status {
	case StatusDraft:
		return "черновик"
	case StatusActive:
		return "опубликована"
	case StatusPaused:
		return "на паузе"
	case StatusArchived:
		return "в архиве"
	}
	return status
}

func publishProblems(sv *Service) map[string]string {
	problems := map[string]string{}
	if len(sv.Tiers) == 0 {
		problems["tiers"] = "Добавьте хотя бы один тариф с ценой и сроком."
	}
	if len(sv.Skills) == 0 {
		problems["skills"] = "Укажите хотя бы один навык — по ним услугу находят."
	}
	if strings.TrimSpace(sv.Summary) == "" {
		problems["summary"] = "Добавьте короткое описание: его видно в каталоге."
	}
	return problems
}

func (s *Svc) requireOwner(ctx context.Context, id *security.Identity, serviceID uuid.UUID) error {
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return httpx.Forbiddenf("only the freelancer who offers a service can change it")
	}
	owner, _, err := s.store.OwnerOf(ctx, serviceID)
	if err != nil {
		return httpx.NotFoundf("service %s does not exist", serviceID)
	}
	if owner != id.UserID {
		// Not yours reads as not found: a service id is not a secret, but
		// confirming ownership boundaries to a stranger costs nothing to avoid.
		s.audit.Denial(ctx, "service", &serviceID, "not the owner")
		return httpx.NotFoundf("service %s does not exist", serviceID)
	}
	return nil
}

func (s *Svc) validate(ctx context.Context, ownerID uuid.UUID, in UpsertRequest) (*newService, error) {
	v := validate.New()
	title := strings.TrimSpace(in.Title)
	summary := strings.TrimSpace(in.Summary)
	description := strings.TrimSpace(in.Description)

	v.Length("title", "Название", title, 8, 120)
	v.NoControlChars("title", "Название", title)
	if summary != "" {
		v.Length("summary", "Краткое описание", summary, 20, 240)
	}
	v.Length("description", "Описание", description, 80, 8000)
	currency := v.Currency("currency", strings.TrimSpace(in.Currency))
	v.IntRange("revisions", "Количество правок", in.Revisions, 0, 10)

	out := &newService{DeveloperID: ownerID, Title: title, Summary: summary, Description: description,
		Currency: currency, Revisions: in.Revisions}

	if slug := strings.TrimSpace(in.CategorySlug); slug == "" {
		v.Add("category_slug", "Выберите категорию услуги.")
	} else if categoryID, err := s.taxonomy.CategoryIDBySlug(ctx, slug); err != nil {
		v.Add("category_slug", "Такой категории нет.")
	} else {
		out.CategoryID = categoryID
	}

	switch n := len(in.Tiers); {
	case n == 0:
		v.Add("tiers", "Добавьте хотя бы один тариф.")
	case n > 3:
		v.Add("tiers", "Тарифов может быть не больше трёх.")
	default:
		var previous int64
		for i, tier := range in.Tiers {
			field := fmt.Sprintf("tiers.%d", i)
			name := strings.TrimSpace(tier.Name)
			v.Length(field+".name", "Название тарифа", name, 2, 40)
			v.MoneyMinor(field+".price_minor", "Цена", tier.PriceMinor, 100, 100_000_000_00)
			v.IntRange(field+".delivery_days", "Срок", tier.DeliveryDays, 1, 365)
			v.IntRange(field+".revisions", "Правки", tier.Revisions, 0, 10)
			if len(tier.Includes) > 10 {
				v.Add(field+".includes", "Не больше десяти пунктов в тарифе.")
			}
			includes := make([]string, 0, len(tier.Includes))
			for _, item := range tier.Includes {
				item = strings.TrimSpace(item)
				if item == "" {
					continue
				}
				if len([]rune(item)) > 80 {
					v.Add(field+".includes", "Каждый пункт — не длиннее 80 символов.")
				}
				includes = append(includes, item)
			}
			if i > 0 && tier.PriceMinor <= previous {
				v.Add(field+".price_minor", "Каждый следующий тариф должен быть дороже предыдущего.")
			}
			previous = tier.PriceMinor
			out.Tiers = append(out.Tiers, TierInput{Name: name, PriceMinor: tier.PriceMinor,
				DeliveryDays: tier.DeliveryDays, Revisions: tier.Revisions, Includes: includes})
		}
	}

	if len(in.Skills) > 12 {
		v.Add("skills", "Не больше двенадцати навыков.")
	} else if len(in.Skills) > 0 {
		ids, unknown, err := s.taxonomy.ResolveSkillIDs(ctx, in.Skills)
		if err != nil {
			return nil, httpx.Internalf(err, "resolve skills")
		}
		if len(unknown) > 0 {
			v.Add("skills", "Неизвестные навыки: "+strings.Join(unknown, ", ")+".")
		}
		out.SkillIDs = ids
	}

	for _, raw := range in.PortfolioIDs {
		pid, err := uuid.Parse(strings.TrimSpace(raw))
		if err != nil {
			v.Add("portfolio_ids", "Неверная ссылка на работу из портфолио.")
			break
		}
		out.PortfolioIDs = append(out.PortfolioIDs, pid)
	}
	if len(out.PortfolioIDs) > 6 {
		v.Add("portfolio_ids", "К услуге можно прикрепить не больше шести работ.")
	}

	if raw := strings.TrimSpace(in.CoverFileID); raw != "" {
		fileID, err := uuid.Parse(raw)
		if err != nil {
			v.Add("cover_file_id", "Неверная ссылка на обложку.")
		} else if ok, err := s.store.OwnedFile(ctx, fileID, ownerID); err != nil {
			return nil, httpx.Internalf(err, "check cover")
		} else if !ok {
			v.Add("cover_file_id", "Обложкой может быть только ваше изображение.")
		} else {
			out.CoverFileID = &fileID
		}
	}

	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}
	return out, nil
}

// flagIfNeeded sends contact details to moderation rather than refusing the
// text: "напишите мне в телеграм" in a service description is a rule broken,
// but a person, not a regex, decides what happens next.
func (s *Svc) flagIfNeeded(ctx context.Context, serviceID uuid.UUID, in UpsertRequest) {
	if s.moderator == nil {
		return
	}
	if found := validate.ContactDetails(in.Description + "\n" + in.Summary); len(found) > 0 {
		s.moderator.Flag(context.WithoutCancel(ctx), "service", serviceID,
			"contains contact details: "+strings.Join(found, ", "))
	}
}

// ── Reading ─────────────────────────────────────────────────────────────────

func (s *Svc) View(ctx context.Context, id *security.Identity, serviceID uuid.UUID) (*Service, error) {
	sv, err := s.store.ByID(ctx, serviceID)
	if err != nil {
		if errors.Is(err, ErrNotFound) {
			return nil, httpx.NotFoundf("service %s does not exist", serviceID)
		}
		return nil, httpx.Internalf(err, "load service")
	}
	owner := id.Authenticated() && id.UserID == sv.Seller.UserID
	live := sv.Status == StatusActive && sv.ModerationState == "approved"
	staff := id.Authenticated() && id.IsModerator()
	if !live && !owner && !staff {
		// A draft or a paused service is the freelancer's business; to anyone
		// else it does not exist.
		return nil, httpx.NotFoundf("service %s does not exist", serviceID)
	}
	sv.IsOwner = owner
	sv.CanOrder = live && id.Authenticated() && id.ActiveRole == security.RoleClient && !owner
	if !owner && !staff {
		sv.ModerationState = ""
		s.store.RecordView(context.WithoutCancel(ctx), serviceID)
	}
	return sv, nil
}

func (s *Svc) Catalogue(ctx context.Context, q Query) ([]Card, map[string]any, error) {
	cards, total, err := s.store.Catalogue(ctx, q)
	if err != nil {
		return nil, nil, httpx.Internalf(err, "list services")
	}
	limit := q.Limit
	if limit <= 0 || limit > 48 {
		limit = 24
	}
	meta := map[string]any{"total": total, "offset": q.Offset, "limit": limit}
	if q.Offset+len(cards) < total {
		meta["next_offset"] = q.Offset + limit
	}
	return cards, meta, nil
}

func (s *Svc) ForSeller(ctx context.Context, id *security.Identity, username string) ([]Card, error) {
	sellerID, err := s.store.SellerIDByUsername(ctx, username)
	if err != nil {
		return nil, httpx.NotFoundf("user %s does not exist", username)
	}
	owner := id.Authenticated() && id.UserID == sellerID
	cards, err := s.store.ForSeller(ctx, sellerID, owner)
	if err != nil {
		return nil, httpx.Internalf(err, "list services")
	}
	return cards, nil
}

func (s *Svc) Mine(ctx context.Context, id *security.Identity) ([]Card, error) {
	if err := security.RequireRole(id, security.RoleDeveloper); err != nil {
		return nil, httpx.Forbiddenf("only a freelancer has services")
	}
	cards, err := s.store.ForSeller(ctx, id.UserID, true)
	if err != nil {
		return nil, httpx.Internalf(err, "list services")
	}
	return cards, nil
}

// ── Ordering ────────────────────────────────────────────────────────────────

// Order turns a tier into a contract. The hidden project behind it exists
// because every contract has one; it is private, already in progress, and
// never reaches a feed.
func (s *Svc) Order(ctx context.Context, id *security.Identity, serviceID uuid.UUID, in OrderRequest) (*contracts.Contract, error) {
	if err := security.RequireRole(id, security.RoleClient); err != nil {
		return nil, httpx.Forbiddenf("switch to your client profile to order a service")
	}
	sv, err := s.store.ByID(ctx, serviceID)
	if err != nil || sv.Status != StatusActive || sv.ModerationState != "approved" {
		return nil, httpx.NotFoundf("service %s does not exist", serviceID)
	}
	if sv.Seller.UserID == id.UserID {
		return nil, httpx.Forbiddenf("you cannot order your own service")
	}

	v := validate.New()
	brief := strings.TrimSpace(in.Brief)
	v.Length("brief", "Описание задачи", brief, 20, 4000)
	if in.Tier == 0 {
		in.Tier = 1
	}
	tier, tierErr := s.store.Tier(ctx, serviceID, in.Tier)
	if tierErr != nil {
		v.Add("tier", "Такого тарифа у этой услуги нет.")
	}
	visibility := strings.TrimSpace(in.PriceVisibility)
	if visibility == "" {
		visibility = "range"
	}
	visibility = v.OneOf("price_visibility", "Видимость цены", visibility, "public", "range", "hidden", "private")
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	title := "Заказ услуги: " + sv.Title
	if len([]rune(title)) > 140 {
		title = string([]rune(title)[:137]) + "…"
	}
	description := brief + "\n\nУслуга: " + sv.Title + " — тариф «" + tier.Name + "» (" +
		fmt.Sprintf("%d", tier.DeliveryDays) + " дн.)"
	price := tier.PriceMinor
	days := tier.DeliveryDays
	projectID, err := s.projects.Create(ctx, projects.NewProject{
		ClientID:       id.UserID,
		Title:          title,
		Summary:        sv.Summary,
		Description:    description,
		CategoryID:     s.categoryID(ctx, sv.Category.Slug),
		BudgetType:     "fixed",
		BudgetMinMinor: &price,
		BudgetMaxMinor: &price,
		Currency:       sv.Currency,
		DurationDays:   &days,
		Visibility:     "private",
		Origin:         "manual",
	})
	if err != nil {
		return nil, httpx.Internalf(err, "create order project")
	}
	if err := s.store.MarkOrderProject(ctx, projectID, sv.Seller.UserID); err != nil {
		return nil, httpx.Internalf(err, "mark order project")
	}

	contract, err := s.contracts.CreateForOrder(ctx, id, contracts.OrderRequest{
		ProjectID:       projectID,
		ClientID:        id.UserID,
		DeveloperID:     sv.Seller.UserID,
		Title:           sv.Title + " — " + tier.Name,
		MilestoneDetail: brief,
		AmountMinor:     tier.PriceMinor,
		Currency:        sv.Currency,
		DeliveryDays:    tier.DeliveryDays,
		PriceVisibility: visibility,
	})
	if err != nil {
		return nil, err
	}
	if err := s.store.RecordOrder(ctx, serviceID); err != nil {
		return nil, httpx.Internalf(err, "count order")
	}
	s.audit.RecordRequest(ctx, audit.Entry{Action: "service.order", SubjectType: "service", SubjectID: &serviceID,
		After: map[string]any{"contract_id": contract.ID, "tier": tier.Position, "amount_minor": tier.PriceMinor}})
	if s.moderator != nil {
		if found := validate.ContactDetails(brief); len(found) > 0 {
			s.moderator.Flag(context.WithoutCancel(ctx), "project", projectID,
				"order brief contains contact details: "+strings.Join(found, ", "))
		}
	}
	return contract, nil
}

func (s *Svc) categoryID(ctx context.Context, slug string) uuid.UUID {
	id, err := s.taxonomy.CategoryIDBySlug(ctx, slug)
	if err != nil {
		return uuid.Nil
	}
	return id
}
