package identity

import (
	"context"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/security"
	"github.com/averix/api/internal/settings"
)

// Gate is the rule that a freelancer proves who they are before money can
// reach them.
//
// It applies to one side of the marketplace only. A client registers, posts
// work and pays — there is nothing about that which needs a passport, and
// asking for one would collect documents the platform has no reason to hold.
// A freelancer is the one who receives money, and that is where the identity
// check belongs.
//
// Where it bites is deliberately narrow: sending a proposal, publishing a
// service, being hired, being ordered. Filling in a profile, browsing work,
// talking to people — none of that is gated, because none of it earns.
type Gate struct {
	db       *database.DB
	settings *settings.Store
}

func NewGate(db *database.DB, set *settings.Store) *Gate {
	return &Gate{db: db, settings: set}
}

// SettingKey lets an operator turn the requirement off for a deployment that
// does not need it. On by default: a marketplace that pays strangers should
// know who they are.
const SettingKey = "identity.required_for_work"

func (g *Gate) Required(ctx context.Context) bool {
	if g == nil || g.settings == nil {
		return false
	}
	return g.settings.Bool(ctx, SettingKey, true)
}

// Require refuses the caller when they have not been verified yet.
func (g *Gate) Require(ctx context.Context, id *security.Identity) error {
	if g == nil || !id.Authenticated() {
		return nil
	}
	// Only freelancers are asked. A client who somehow reaches one of these
	// calls is refused by the role check that sits next to this one, not by a
	// demand for documents they were never asked for.
	if !id.HasRole(security.RoleDeveloper) {
		return nil
	}
	if !g.Required(ctx) || id.IdentityVerified {
		return nil
	}
	return notVerified("Чтобы брать оплачиваемую работу, подтвердите личность. Это делается один раз и занимает пару минут.")
}

// RequireUser is the same rule applied to the other side of a deal: hiring
// somebody, or ordering their service. The session belongs to the client, so
// the answer has to come from the database.
func (g *Gate) RequireUser(ctx context.Context, userID uuid.UUID) error {
	if g == nil || !g.Required(ctx) {
		return nil
	}
	var verified bool
	err := g.db.QueryRow(ctx, `
		SELECT u.identity_verified_at IS NOT NULL
		FROM users u
		WHERE u.id = $1
		  AND EXISTS (SELECT 1 FROM user_roles r WHERE r.user_id = u.id AND r.role = 'developer')`,
		userID).Scan(&verified)
	if database.IsNoRows(err) {
		// Not a freelancer at all: this rule has nothing to say about them.
		return nil
	}
	if err != nil {
		return httpx.Internalf(err, "check identity verification")
	}
	if verified {
		return nil
	}
	return notVerified("Этот исполнитель ещё не подтвердил личность. Работать с ним можно будет, как только он это сделает.")
}

func notVerified(message string) error {
	e := *httpx.ErrForbidden
	e.Code = "identity_not_verified"
	e.Message = message
	return &e
}
