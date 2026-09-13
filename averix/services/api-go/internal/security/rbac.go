// Package security holds the authorisation model: who a caller is, what role
// they are acting in, and whether they may touch a given resource.
//
// Two layers, both required:
//
//	Role permissions   — "may a developer submit proposals at all?"
//	Resource policies  — "may THIS developer read THIS contract?"
//
// The second is the one that stops IDOR. Changing /projects/{a} to
// /projects/{b} fails not because the id is unguessable but because every
// protected read asks a policy whether the caller is a party to it.
package security

import (
	"context"
	"fmt"

	"github.com/google/uuid"
)

type Role string

const (
	RoleClient    Role = "client"
	RoleDeveloper Role = "developer"
	RoleModerator Role = "moderator"
	RoleAdmin     Role = "admin"
)

func (r Role) Valid() bool {
	switch r {
	case RoleClient, RoleDeveloper, RoleModerator, RoleAdmin:
		return true
	}
	return false
}

// Permission names a capability. Kept coarse on purpose: a permission per
// endpoint would be unmaintainable, and a permission per domain action is what
// the admin panel actually needs to display.
type Permission string

const (
	// Client capabilities
	PermProjectCreate   Permission = "project.create"
	PermProjectManage   Permission = "project.manage"
	PermProposalReview  Permission = "proposal.review"
	PermDeveloperInvite Permission = "developer.invite"
	PermMilestoneFund   Permission = "milestone.fund"
	PermMilestoneReview Permission = "milestone.review"
	PermSaveDeveloper   Permission = "developer.save"

	// Developer capabilities
	PermProposalSubmit  Permission = "proposal.submit"
	PermPortfolioManage Permission = "portfolio.manage"
	PermServiceManage   Permission = "service.manage"
	PermGitHubConnect   Permission = "github.connect"
	PermMilestoneSubmit Permission = "milestone.submit"
	PermSaveProject     Permission = "project.save"

	// Shared
	PermMessageSend   Permission = "message.send"
	PermFileUpload    Permission = "file.upload"
	PermReviewWrite   Permission = "review.write"
	PermDisputeOpen   Permission = "dispute.open"
	PermProfileManage Permission = "profile.manage"

	// Moderation
	PermModerationQueue  Permission = "moderation.queue"
	PermModerationDecide Permission = "moderation.decide"
	PermReportReview     Permission = "report.review"
	PermContentHide      Permission = "content.hide"

	// Administration
	PermUserView          Permission = "users.view"
	PermUserManage        Permission = "user.manage"
	PermUserSuspend       Permission = "users.suspend"
	PermUserBan           Permission = "users.ban"
	PermRoleGrant         Permission = "role.grant"
	PermPaymentView       Permission = "payments.view"
	PermPaymentManage     Permission = "payment.manage"
	PermPaymentRelease    Permission = "payment.release"
	PermSecurityView      Permission = "security.view"
	PermDisputeResolve    Permission = "dispute.resolve"
	PermSettingsManage    Permission = "settings.manage"
	PermAuditRead         Permission = "audit.read"
	PermAdminDashboard    Permission = "admin.dashboard"
	PermMatchingConfigure Permission = "matching.configure"

	// Identity documents.
	//
	// Deliberately absent from every role's grant table below. A passport is
	// not something a person should be able to look at because somebody made
	// them a moderator; these two are granted by name, to one account at a
	// time, and the grant is recorded in admin_permission_grants.
	PermIdentityView   Permission = "identity_verification.view"
	PermIdentityReview Permission = "identity_verification.review"
)

// grantableByName is the set of permissions an administrator may hand to
// another account on top of what its role already gives.
//
// A closed list on purpose: an endpoint that accepted any string would let a
// typo create a permission nothing checks, and a well-chosen string create one
// that everything does.
var grantableByName = set(
	PermIdentityView, PermIdentityReview,
	PermPaymentView, PermSecurityView, PermAuditRead, PermUserView,
)

// Grantable reports whether a permission may be granted to an account by name.
func Grantable(p Permission) bool {
	_, ok := grantableByName[p]
	return ok
}

// GrantablePermissions lists what an administrator may hand out, for the panel.
func GrantablePermissions() []Permission {
	return []Permission{
		PermIdentityView, PermIdentityReview,
		PermPaymentView, PermSecurityView, PermAuditRead, PermUserView,
	}
}

// rolePermissions is the whole grant table. Admin is listed explicitly rather
// than given a wildcard, so adding a permission is a deliberate decision about
// who gets it instead of something admin silently inherits.
var rolePermissions = map[Role]map[Permission]struct{}{
	RoleClient: set(
		PermProjectCreate, PermProjectManage, PermProposalReview,
		PermDeveloperInvite, PermMilestoneFund, PermMilestoneReview,
		PermSaveDeveloper, PermMessageSend, PermFileUpload, PermReviewWrite,
		PermDisputeOpen, PermProfileManage,
	),
	RoleDeveloper: set(
		PermProposalSubmit, PermPortfolioManage, PermServiceManage,
		PermGitHubConnect, PermMilestoneSubmit, PermSaveProject,
		PermMessageSend, PermFileUpload, PermReviewWrite, PermDisputeOpen,
		PermProfileManage,
	),
	RoleModerator: set(
		PermModerationQueue, PermModerationDecide, PermReportReview,
		PermContentHide, PermAdminDashboard, PermUserView, PermProfileManage,
	),
	RoleAdmin: set(
		PermModerationQueue, PermModerationDecide, PermReportReview,
		PermContentHide, PermAdminDashboard, PermUserView, PermUserManage,
		PermUserSuspend, PermUserBan, PermRoleGrant,
		PermPaymentView, PermPaymentManage, PermPaymentRelease,
		PermSecurityView, PermDisputeResolve,
		PermSettingsManage, PermAuditRead, PermMatchingConfigure,
		PermProfileManage,
	),
}

func set(perms ...Permission) map[Permission]struct{} {
	m := make(map[Permission]struct{}, len(perms))
	for _, p := range perms {
		m[p] = struct{}{}
	}
	return m
}

// Identity is the authenticated caller. ActiveRole is the interface they are
// currently in, which is why a dual-role account cannot act as a client on a
// developer screen: the session carries one role, not a set.
type Identity struct {
	UserID     uuid.UUID
	SessionID  uuid.UUID
	Username   string
	Email      string
	ActiveRole Role
	// Every role the account holds, for the role switcher.
	Roles []Role
	// Permissions granted to this account by name, on top of its role. Empty
	// for everyone who is not staff.
	Granted          []Permission
	Status           string
	EmailVerified    bool
	IdentityVerified bool
	CSRFToken        string
}

func (i *Identity) Authenticated() bool { return i != nil && i.UserID != uuid.Nil }

// HasRole reports whether the account holds a role, regardless of which one is
// active. Used for the role switcher, never for authorisation.
func (i *Identity) HasRole(r Role) bool {
	if i == nil {
		return false
	}
	for _, have := range i.Roles {
		if have == r {
			return true
		}
	}
	return false
}

func (i *Identity) IsAdmin() bool     { return i.HasRole(RoleAdmin) }
func (i *Identity) IsModerator() bool { return i.HasRole(RoleAdmin) || i.HasRole(RoleModerator) }

// Can reports whether the caller's active role grants a permission.
//
// Deliberately checks ActiveRole and not the full role set: an admin browsing
// the product as a client must not carry admin powers into client screens.
// Staff use the admin interface, where their session's active role is admin.
func (i *Identity) Can(p Permission) bool {
	if !i.Authenticated() {
		return false
	}
	if i.Status != "active" {
		return false
	}
	// A permission granted by name still requires the caller to be acting in a
	// staff role: an administrator browsing the marketplace as a client must
	// not carry the right to open someone's passport into a client screen.
	if i.ActiveRole == RoleAdmin || i.ActiveRole == RoleModerator {
		for _, granted := range i.Granted {
			if granted == p {
				return true
			}
		}
	}
	perms, ok := rolePermissions[i.ActiveRole]
	if !ok {
		return false
	}
	_, granted := perms[p]
	return granted
}

// Permissions lists what the active role can do, so the web app can hide
// actions the caller could not perform anyway.
func (i *Identity) Permissions() []string {
	if !i.Authenticated() {
		return nil
	}
	perms := rolePermissions[i.ActiveRole]
	out := make([]string, 0, len(perms)+len(i.Granted))
	for p := range perms {
		out = append(out, string(p))
	}
	if i.ActiveRole == RoleAdmin || i.ActiveRole == RoleModerator {
		for _, p := range i.Granted {
			if _, already := perms[p]; !already {
				out = append(out, string(p))
			}
		}
	}
	return out
}

// Owns reports whether a resource belongs to the caller.
func (i *Identity) Owns(ownerID uuid.UUID) bool {
	return i.Authenticated() && ownerID != uuid.Nil && i.UserID == ownerID
}

// ── Context plumbing ────────────────────────────────────────────────────────

type ctxKey int

const ctxIdentity ctxKey = iota

func WithIdentity(ctx context.Context, id *Identity) context.Context {
	return context.WithValue(ctx, ctxIdentity, id)
}

// FromContext returns the caller, or nil when the request is anonymous.
func FromContext(ctx context.Context) *Identity {
	if v, ok := ctx.Value(ctxIdentity).(*Identity); ok {
		return v
	}
	return nil
}

// ── Denials ─────────────────────────────────────────────────────────────────

// Denial explains a refusal. Reason is for the audit log; the HTTP layer turns
// this into a generic 403 so the caller learns nothing about what exists.
type Denial struct {
	Subject string
	Action  string
	Reason  string
}

func (d *Denial) Error() string {
	return fmt.Sprintf("denied %s on %s: %s", d.Action, d.Subject, d.Reason)
}

func Deny(subject, action, reason string) error {
	return &Denial{Subject: subject, Action: action, Reason: reason}
}

// ── Resource policies ───────────────────────────────────────────────────────

// Party is a resource's participants, as loaded from the database. Policies
// operate on this rather than reaching into each domain's model, so the rules
// live in one place and read the same for every resource.
type Party struct {
	OwnerID      uuid.UUID
	ClientID     uuid.UUID
	DeveloperID  uuid.UUID
	Participants []uuid.UUID
	// Whether the resource is visible without being a party to it.
	Public bool
	// Set for a soft-deleted or hidden resource.
	Withdrawn bool
}

func (p Party) includes(userID uuid.UUID) bool {
	if userID == uuid.Nil {
		return false
	}
	if p.OwnerID == userID || p.ClientID == userID || p.DeveloperID == userID {
		return true
	}
	for _, id := range p.Participants {
		if id == userID {
			return true
		}
	}
	return false
}

// CanRead is the single gate for reading a protected resource.
//
// An admin may read anything — that is what an admin is for — but the caller is
// expected to write an audit entry when that is the branch taken, which is why
// this returns the reason it allowed access.
func CanRead(id *Identity, subject string, p Party) error {
	if p.Public && !p.Withdrawn {
		return nil
	}
	if !id.Authenticated() {
		return Deny(subject, "read", "not authenticated")
	}
	if p.includes(id.UserID) {
		return nil
	}
	// Staff read access is granted by the session's active role, so an admin
	// browsing as a client does not carry it into client screens.
	if id.ActiveRole == RoleAdmin || id.ActiveRole == RoleModerator {
		return nil
	}
	return Deny(subject, "read", "caller is not a party to this resource")
}

// CanWrite is stricter than CanRead: a moderator may inspect content but only
// a party or an admin may change it.
func CanWrite(id *Identity, subject string, p Party) error {
	if !id.Authenticated() {
		return Deny(subject, "write", "not authenticated")
	}
	if p.Withdrawn {
		return Deny(subject, "write", "resource is withdrawn")
	}
	if p.includes(id.UserID) {
		return nil
	}
	if id.ActiveRole == RoleAdmin {
		return nil
	}
	return Deny(subject, "write", "caller is not a party to this resource")
}

// RequireOwner allows only the owner, with no admin bypass. Used where even an
// admin acting through the product interface must not write on someone's
// behalf: their own profile, their own portfolio, their own proposals.
func RequireOwner(id *Identity, subject string, ownerID uuid.UUID) error {
	if !id.Authenticated() {
		return Deny(subject, "write", "not authenticated")
	}
	if id.UserID != ownerID {
		return Deny(subject, "write", "caller does not own this resource")
	}
	return nil
}

// RequireRole allows only a caller acting in one of the given roles.
func RequireRole(id *Identity, roles ...Role) error {
	if !id.Authenticated() {
		return Deny("endpoint", "access", "not authenticated")
	}
	for _, r := range roles {
		if id.ActiveRole == r {
			return nil
		}
	}
	return Deny("endpoint", "access",
		fmt.Sprintf("active role %q is not one of the required roles", id.ActiveRole))
}

// RequirePermission allows only a caller whose active role grants it.
func RequirePermission(id *Identity, p Permission) error {
	if !id.Authenticated() {
		return Deny(string(p), "access", "not authenticated")
	}
	if !id.Can(p) {
		return Deny(string(p), "access",
			fmt.Sprintf("role %q does not grant %s", id.ActiveRole, p))
	}
	return nil
}
