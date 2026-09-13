// Package clients owns the hiring side's profile and dashboard summary.
//
// A client profile is much lighter than a developer's: a client is judged on
// how they behave in a contract, not on a portfolio, so the profile exists
// mainly to give developers enough context to decide whether to bid.
package clients

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/money"
	"github.com/averix/api/internal/platform/places"
	"github.com/averix/api/internal/platform/urlguard"
	"github.com/averix/api/internal/platform/validate"
	"github.com/averix/api/internal/security"
)

type Profile struct {
	UserID   uuid.UUID `json:"user_id"`
	Username string    `json:"username"`
	FullName string    `json:"full_name"`
	Email    string    `json:"email,omitempty"`

	CompanyName    string `json:"company_name,omitempty"`
	CompanyWebsite string `json:"company_website,omitempty"`
	CompanySize    string `json:"company_size,omitempty"`
	Industry       string `json:"industry,omitempty"`
	About          string `json:"about,omitempty"`

	CountryCode string `json:"country_code,omitempty"`
	City        string `json:"city,omitempty"`
	Timezone    string `json:"timezone,omitempty"`

	// Hiring history. A developer deciding whether to spend an hour on a
	// proposal needs to know whether this client has ever hired anyone.
	ProjectsPosted   int      `json:"projects_posted"`
	HiresMade        int      `json:"hires_made"`
	RatingAvg        *float64 `json:"rating_avg,omitempty"`
	RatingCount      int      `json:"rating_count"`
	PaymentVerified  bool     `json:"payment_verified"`
	IdentityVerified bool     `json:"identity_verified"`

	// Private to the owner and staff: what a client has spent is not a
	// developer's business.
	//
	// One row per currency rather than one number. A client who paid in
	// roubles and in dollars has no single total, and adding the two would
	// produce a figure that is wrong in both.
	Spent []SpentRow `json:"spent,omitempty"`

	MemberSince time.Time  `json:"member_since"`
	LastSeenAt  *time.Time `json:"last_seen_at,omitempty"`
}

// SpentRow is what a client has paid out in one currency.
type SpentRow struct {
	Currency string `json:"currency"`
	Minor    int64  `json:"minor"`
	Display  string `json:"display"`
}

// PublicProfile is what a developer sees when deciding whether to bid.
type PublicProfile struct {
	UserID   uuid.UUID `json:"user_id"`
	Username string    `json:"username"`
	// The display name is the company when there is one, otherwise the person.
	DisplayName string `json:"display_name"`
	CompanyName string `json:"company_name,omitempty"`
	CompanySize string `json:"company_size,omitempty"`
	Industry    string `json:"industry,omitempty"`
	About       string `json:"about,omitempty"`
	Location    string `json:"location,omitempty"`

	ProjectsPosted   int      `json:"projects_posted"`
	HiresMade        int      `json:"hires_made"`
	RatingAvg        *float64 `json:"rating_avg,omitempty"`
	RatingCount      int      `json:"rating_count"`
	PaymentVerified  bool     `json:"payment_verified"`
	IdentityVerified bool     `json:"identity_verified"`
	// Derived so a developer can see at a glance whether bidding is worthwhile.
	HireRate *float64 `json:"hire_rate,omitempty"`

	MemberSince time.Time `json:"member_since"`
}

type Store struct{ db *database.DB }

func NewStore(db *database.DB) *Store { return &Store{db: db} }

var ErrNotFound = errors.New("client profile not found")

const clientSelect = `
	SELECT u.id, u.username, u.full_name, u.email, u.country_code, u.city, u.timezone,
	       u.identity_verified_at IS NOT NULL, u.last_seen_at, u.created_at,
	       c.company_name, c.company_website, c.company_size, c.industry, c.about,
	       c.projects_posted, c.hires_made,
	       c.rating_avg, c.rating_count, c.payment_verified_at IS NOT NULL
	FROM users u
	JOIN client_profiles c ON c.user_id = u.id
	WHERE u.deleted_at IS NULL`

func (s *Store) scan(ctx context.Context, where string, arg any) (*Profile, error) {
	var p Profile
	var (
		country, city, tz                       *string
		company, website, size, industry, about *string
	)
	err := s.db.QueryRow(ctx, clientSelect+" AND "+where, arg).Scan(
		&p.UserID, &p.Username, &p.FullName, &p.Email, &country, &city, &tz,
		&p.IdentityVerified, &p.LastSeenAt, &p.MemberSince,
		&company, &website, &size, &industry, &about,
		&p.ProjectsPosted, &p.HiresMade,
		&p.RatingAvg, &p.RatingCount, &p.PaymentVerified)
	if database.IsNoRows(err) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("scan client profile: %w", err)
	}
	p.CountryCode = deref(country)
	p.City = deref(city)
	p.Timezone = deref(tz)
	p.CompanyName = deref(company)
	p.CompanyWebsite = deref(website)
	p.CompanySize = deref(size)
	p.Industry = deref(industry)
	p.About = deref(about)

	spent, err := s.spent(ctx, p.UserID)
	if err != nil {
		return nil, err
	}
	p.Spent = spent
	return &p, nil
}

// spent totals the payments a client actually made, per currency.
//
// Read from the payments themselves rather than from a counter: the column
// that used to hold this was never written to, so every client's spend read
// as zero for as long as the product has existed. A figure nobody maintains
// is worse than no figure at all — this one cannot drift, because there is
// nothing to keep in step.
func (s *Store) spent(ctx context.Context, userID uuid.UUID) ([]SpentRow, error) {
	rows, err := s.db.Query(ctx, `
		SELECT currency, sum(amount_minor - coalesce(refunded_minor, 0))
		FROM payment_intents
		WHERE payer_id = $1 AND direction = 'charge' AND status = 'succeeded'
		GROUP BY currency
		HAVING sum(amount_minor - coalesce(refunded_minor, 0)) > 0
		ORDER BY 2 DESC`, userID)
	if err != nil {
		return nil, fmt.Errorf("total client spend: %w", err)
	}
	defer rows.Close()

	out := []SpentRow{}
	for rows.Next() {
		var row SpentRow
		if err := rows.Scan(&row.Currency, &row.Minor); err != nil {
			return nil, fmt.Errorf("scan client spend: %w", err)
		}
		row.Display = money.Format(row.Minor, row.Currency)
		out = append(out, row)
	}
	return out, rows.Err()
}

func (s *Store) ByID(ctx context.Context, id uuid.UUID) (*Profile, error) {
	return s.scan(ctx, "u.id = $1", id)
}

func (s *Store) ByUsername(ctx context.Context, username string) (*Profile, error) {
	return s.scan(ctx, "u.username = $1", strings.ToLower(strings.TrimSpace(username)))
}

type UpdateInput struct {
	FullName       string
	CompanyName    string
	CompanyWebsite string
	CompanySize    string
	Industry       string
	About          string
	CountryCode    string
	City           string
	Timezone       string
}

func (s *Store) Update(ctx context.Context, userID uuid.UUID, in UpdateInput) error {
	return s.db.InTx(ctx, func(q database.Querier) error {
		if _, err := q.Exec(ctx, `
			UPDATE users SET full_name = coalesce(nullif($2, ''), full_name),
			                 country_code = $3, city = $4,
			                 timezone = coalesce(nullif($5, ''), timezone),
			                 updated_at = now()
			WHERE id = $1`,
			userID, in.FullName, nullIfBlank(strings.ToUpper(in.CountryCode)),
			nullIfBlank(in.City), in.Timezone); err != nil {
			return fmt.Errorf("update user: %w", err)
		}
		if _, err := q.Exec(ctx, `
			UPDATE client_profiles SET
			  company_name    = $2,
			  company_website = $3,
			  company_size    = $4,
			  industry        = $5,
			  about           = $6,
			  updated_at      = now()
			WHERE user_id = $1`,
			userID, nullIfBlank(in.CompanyName), nullIfBlank(in.CompanyWebsite),
			nullIfBlank(in.CompanySize), nullIfBlank(in.Industry),
			nullIfBlank(in.About)); err != nil {
			return fmt.Errorf("update client profile: %w", err)
		}
		return nil
	})
}

// ── Service ─────────────────────────────────────────────────────────────────

type Service struct {
	store *Store
}

func NewService(store *Store) *Service { return &Service{store: store} }

// companyWebsiteRules are deliberately strict in every environment.
//
// Unlike a portfolio project URL — which a developer genuinely may point at
// localhost while building — a company website is published to developers
// deciding whether to bid. No development workflow needs http://localhost
// there, so loopback is never allowed for this field.
func companyWebsiteRules() urlguard.Options { return urlguard.DefaultOptions() }

func (s *Service) Me(ctx context.Context, id *security.Identity) (*Profile, error) {
	if !id.Authenticated() {
		return nil, httpx.ErrUnauthenticated
	}
	profile, err := s.store.ByID(ctx, id.UserID)
	if errors.Is(err, ErrNotFound) {
		return nil, httpx.NotFoundf("no client profile for user %s", id.UserID)
	}
	if err != nil {
		return nil, httpx.Internalf(err, "load client profile")
	}
	return profile, nil
}

func (s *Service) Public(ctx context.Context, username string) (*PublicProfile, error) {
	profile, err := s.store.ByUsername(ctx, username)
	if errors.Is(err, ErrNotFound) {
		return nil, httpx.NotFoundf("no client profile for username %q", username)
	}
	if err != nil {
		return nil, httpx.Internalf(err, "load client profile")
	}

	display := profile.CompanyName
	if display == "" {
		display = profile.FullName
	}
	out := &PublicProfile{
		UserID:           profile.UserID,
		Username:         profile.Username,
		DisplayName:      display,
		CompanyName:      profile.CompanyName,
		CompanySize:      profile.CompanySize,
		Industry:         profile.Industry,
		About:            profile.About,
		Location:         formatLocation(profile.City, profile.CountryCode),
		ProjectsPosted:   profile.ProjectsPosted,
		HiresMade:        profile.HiresMade,
		RatingAvg:        profile.RatingAvg,
		RatingCount:      profile.RatingCount,
		PaymentVerified:  profile.PaymentVerified,
		IdentityVerified: profile.IdentityVerified,
		MemberSince:      profile.MemberSince,
	}
	// Spend is deliberately absent: a developer does not need it, and a
	// client's budget history is not public information.
	if profile.ProjectsPosted > 0 {
		rate := float64(profile.HiresMade) / float64(profile.ProjectsPosted) * 100
		out.HireRate = &rate
	}
	return out, nil
}

type UpdateRequest struct {
	FullName       string `json:"full_name"`
	CompanyName    string `json:"company_name"`
	CompanyWebsite string `json:"company_website"`
	CompanySize    string `json:"company_size"`
	Industry       string `json:"industry"`
	About          string `json:"about"`
	CountryCode    string `json:"country_code"`
	City           string `json:"city"`
	Timezone       string `json:"timezone"`
}

func (s *Service) Update(ctx context.Context, id *security.Identity, in UpdateRequest) (*Profile, error) {
	if !id.Authenticated() {
		return nil, httpx.ErrUnauthenticated
	}
	if err := security.RequireRole(id, security.RoleClient); err != nil {
		return nil, httpx.ErrForbidden.Wrap(err)
	}

	v := validate.New()
	if in.FullName != "" {
		v.Length("full_name", "Имя и фамилия", in.FullName, 2, 120)
		v.NoControlChars("full_name", "Имя и фамилия", in.FullName)
	}
	if in.CompanyName != "" {
		v.Length("company_name", "Название компании", in.CompanyName, 2, 120)
	}
	if in.CompanySize != "" {
		v.OneOf("company_size", "Размер компании", in.CompanySize,
			"solo", "2-10", "11-50", "51-200", "200+")
	}
	if in.About != "" {
		v.Length("about", "О компании", in.About, 0, 2000)
		v.NoControlChars("about", "О компании", in.About)
	}
	if in.CountryCode != "" && len(in.CountryCode) != 2 {
		v.Add("country_code", "Код страны — две латинские буквы.")
	}

	// A company website is a user-supplied URL, so it goes through the same
	// guard as a portfolio link: no javascript:, no internal addresses.
	website := ""
	if strings.TrimSpace(in.CompanyWebsite) != "" {
		result, err := urlguard.Normalise(in.CompanyWebsite, companyWebsiteRules())
		if err != nil {
			var rejection *urlguard.Rejection
			if errors.As(err, &rejection) {
				v.Add("company_website", rejection.Human())
			} else {
				v.Add("company_website", "Такой адрес сайта не подходит.")
			}
		} else {
			website = result.URL
		}
	}
	if v.Any() {
		return nil, httpx.Validation(v.Fields())
	}

	if err := s.store.Update(ctx, id.UserID, UpdateInput{
		FullName:       strings.TrimSpace(in.FullName),
		CompanyName:    strings.TrimSpace(in.CompanyName),
		CompanyWebsite: website,
		CompanySize:    in.CompanySize,
		Industry:       strings.TrimSpace(in.Industry),
		About:          strings.TrimSpace(in.About),
		CountryCode:    in.CountryCode,
		City:           strings.TrimSpace(in.City),
		Timezone:       strings.TrimSpace(in.Timezone),
	}); err != nil {
		return nil, httpx.Internalf(err, "update client profile")
	}
	return s.Me(ctx, id)
}

// ── HTTP ────────────────────────────────────────────────────────────────────

type Handlers struct{ svc *Service }

func NewHandlers(svc *Service) *Handlers { return &Handlers{svc: svc} }

type Middleware struct {
	Require       httpx.Middleware
	CSRF          httpx.Middleware
	RequireClient httpx.Middleware
}

func (h *Handlers) Register(r *httpx.Router, mw Middleware) {
	// A client's public page is visible to signed-in developers only: it is
	// context for bidding, not a public directory entry.
	authed := r.Group("/clients", mw.Require)
	authed.GET("/{username}", h.publicProfile)

	me := r.Group("/clients/me", mw.Require, mw.RequireClient, mw.CSRF)
	me.GET("", h.me)
	me.PUT("", h.update)
}

func (h *Handlers) me(w http.ResponseWriter, r *http.Request) error {
	profile, err := h.svc.Me(r.Context(), security.FromContext(r.Context()))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, profile)
}

func (h *Handlers) publicProfile(w http.ResponseWriter, r *http.Request) error {
	profile, err := h.svc.Public(r.Context(), r.PathValue("username"))
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, profile)
}

func (h *Handlers) update(w http.ResponseWriter, r *http.Request) error {
	var body UpdateRequest
	if err := httpx.DecodeJSON(w, r, &body, 16<<10); err != nil {
		return err
	}
	profile, err := h.svc.Update(r.Context(), security.FromContext(r.Context()), body)
	if err != nil {
		return err
	}
	return httpx.JSON(w, http.StatusOK, profile)
}

func formatLocation(city, country string) string {
	return places.Format(city, country)
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

func nullIfBlank(s string) any {
	if strings.TrimSpace(s) == "" {
		return nil
	}
	return s
}
