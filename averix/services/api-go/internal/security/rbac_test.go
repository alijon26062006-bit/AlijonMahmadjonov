package security

import (
	"testing"

	"github.com/google/uuid"
)

func ident(role Role, roles ...Role) *Identity {
	if len(roles) == 0 {
		roles = []Role{role}
	}
	return &Identity{
		UserID:     uuid.New(),
		ActiveRole: role,
		Roles:      roles,
		Status:     "active",
	}
}

func TestRolePermissionsAreSeparated(t *testing.T) {
	client := ident(RoleClient)
	dev := ident(RoleDeveloper)

	if !client.Can(PermProjectCreate) {
		t.Error("a client must be able to create a project")
	}
	if client.Can(PermProposalSubmit) {
		t.Error("a client must not be able to submit a proposal")
	}
	if client.Can(PermPortfolioManage) {
		t.Error("a client must not be able to manage a developer portfolio")
	}

	if !dev.Can(PermProposalSubmit) {
		t.Error("a developer must be able to submit a proposal")
	}
	if dev.Can(PermProjectCreate) {
		t.Error("a developer must not be able to create a project")
	}
	if dev.Can(PermMilestoneReview) {
		t.Error("a developer must not be able to approve their own milestone")
	}
	if !dev.Can(PermMilestoneSubmit) {
		t.Error("a developer must be able to submit a milestone")
	}
}

// Money, roles and account status are admin-only, and nothing else comes close
// to them. This is the test that fails if a permission is added to the wrong row.
func TestPrivilegedPermissionsAreAdminOnly(t *testing.T) {
	privileged := []Permission{
		PermUserManage, PermRoleGrant, PermPaymentManage, PermPaymentRelease,
		PermDisputeResolve, PermSettingsManage, PermAuditRead, PermMatchingConfigure,
	}
	for _, role := range []Role{RoleClient, RoleDeveloper, RoleModerator} {
		id := ident(role)
		for _, p := range privileged {
			if id.Can(p) {
				t.Errorf("role %q must not hold the privileged permission %s", role, p)
			}
		}
	}
	admin := ident(RoleAdmin)
	for _, p := range privileged {
		if !admin.Can(p) {
			t.Errorf("an admin must hold %s", p)
		}
	}
}

func TestModeratorCannotTouchMoneyOrRoles(t *testing.T) {
	mod := ident(RoleModerator)
	if !mod.Can(PermModerationDecide) {
		t.Error("a moderator must be able to decide a moderation item")
	}
	for _, p := range []Permission{PermPaymentRelease, PermRoleGrant, PermUserManage, PermDisputeResolve} {
		if mod.Can(p) {
			t.Errorf("a moderator must not hold %s", p)
		}
	}
}

// A suspended account keeps its roles but loses every capability, so a
// suspension takes effect without having to strip role rows.
func TestSuspendedAccountCanDoNothing(t *testing.T) {
	id := ident(RoleDeveloper)
	id.Status = "suspended"
	for _, p := range []Permission{PermProposalSubmit, PermMessageSend, PermFileUpload, PermPortfolioManage} {
		if id.Can(p) {
			t.Errorf("a suspended account must not hold %s", p)
		}
	}
}

func TestAnonymousCallerHasNothing(t *testing.T) {
	var anon *Identity
	if anon.Authenticated() {
		t.Fatal("a nil identity must not be authenticated")
	}
	if anon.Can(PermMessageSend) {
		t.Error("an anonymous caller must hold no permissions")
	}
	if anon.IsAdmin() {
		t.Error("an anonymous caller must not be an admin")
	}
	if len(anon.Permissions()) != 0 {
		t.Error("an anonymous caller must list no permissions")
	}
}

// The active role is what authorises, not the set of roles held. An account
// with both roles acting as a client must not gain developer capabilities.
func TestActiveRoleDecidesNotTheRoleSet(t *testing.T) {
	dual := ident(RoleClient, RoleClient, RoleDeveloper)
	if !dual.Can(PermProjectCreate) {
		t.Error("acting as a client, project creation must be allowed")
	}
	if dual.Can(PermProposalSubmit) {
		t.Error("acting as a client, proposal submission must be refused even though the developer role is held")
	}
	if !dual.HasRole(RoleDeveloper) {
		t.Error("HasRole must still report the developer role for the role switcher")
	}

	// An admin browsing the product as a client carries no admin powers.
	adminAsClient := ident(RoleClient, RoleClient, RoleAdmin)
	if adminAsClient.Can(PermPaymentRelease) {
		t.Error("an admin acting as a client must not be able to release payments")
	}
	if !adminAsClient.IsAdmin() {
		t.Error("IsAdmin must still report the held role")
	}
}

// This is the IDOR test. The only thing that grants access to someone else's
// contract is being a party to it.
func TestCanReadRequiresMembership(t *testing.T) {
	client := ident(RoleClient)
	dev := ident(RoleDeveloper)
	stranger := ident(RoleDeveloper)

	contract := Party{ClientID: client.UserID, DeveloperID: dev.UserID}

	if err := CanRead(client, "contract", contract); err != nil {
		t.Errorf("the client on a contract must be able to read it: %v", err)
	}
	if err := CanRead(dev, "contract", contract); err != nil {
		t.Errorf("the developer on a contract must be able to read it: %v", err)
	}
	if err := CanRead(stranger, "contract", contract); err == nil {
		t.Error("a developer who is not on the contract must not be able to read it")
	}
	if err := CanRead(nil, "contract", contract); err == nil {
		t.Error("an anonymous caller must not be able to read a private contract")
	}

	// Swapping one id for another — the /projects/100 -> /projects/101 case —
	// still fails, because the check is membership and not id shape.
	other := Party{ClientID: uuid.New(), DeveloperID: uuid.New()}
	if err := CanRead(client, "contract", other); err == nil {
		t.Error("reading a different contract by changing the id must be refused")
	}
}

func TestCanReadAllowsPublicResources(t *testing.T) {
	public := Party{OwnerID: uuid.New(), Public: true}
	if err := CanRead(nil, "developer_profile", public); err != nil {
		t.Errorf("an anonymous visitor must be able to read a public profile: %v", err)
	}
	withdrawn := Party{OwnerID: uuid.New(), Public: true, Withdrawn: true}
	if err := CanRead(nil, "developer_profile", withdrawn); err == nil {
		t.Error("a withdrawn resource must not be publicly readable")
	}
}

func TestObserverParticipantCanRead(t *testing.T) {
	observer := ident(RoleClient)
	p := Party{
		ClientID:     uuid.New(),
		DeveloperID:  uuid.New(),
		Participants: []uuid.UUID{observer.UserID},
	}
	if err := CanRead(observer, "contract", p); err != nil {
		t.Errorf("a listed participant must be able to read: %v", err)
	}
}

func TestCanWriteIsStricterThanCanRead(t *testing.T) {
	mod := ident(RoleModerator)
	p := Party{ClientID: uuid.New(), DeveloperID: uuid.New()}

	if err := CanRead(mod, "contract", p); err != nil {
		t.Errorf("a moderator must be able to inspect a contract: %v", err)
	}
	if err := CanWrite(mod, "contract", p); err == nil {
		t.Error("a moderator must not be able to modify a contract")
	}

	admin := ident(RoleAdmin)
	if err := CanWrite(admin, "contract", p); err != nil {
		t.Errorf("an admin must be able to modify a contract: %v", err)
	}
}

func TestCanWriteRefusesWithdrawnResources(t *testing.T) {
	owner := ident(RoleDeveloper)
	p := Party{OwnerID: owner.UserID, Withdrawn: true}
	if err := CanWrite(owner, "portfolio_project", p); err == nil {
		t.Error("writing to a withdrawn resource must be refused even for its owner")
	}
}

// Some resources have no admin bypass: nobody writes another person's profile
// or portfolio through the product interface.
func TestRequireOwnerHasNoAdminBypass(t *testing.T) {
	owner := ident(RoleDeveloper)
	admin := ident(RoleAdmin)

	if err := RequireOwner(owner, "portfolio_project", owner.UserID); err != nil {
		t.Errorf("the owner must be allowed: %v", err)
	}
	if err := RequireOwner(admin, "portfolio_project", owner.UserID); err == nil {
		t.Error("an admin must not be able to write someone else's portfolio through the product interface")
	}
	if err := RequireOwner(nil, "portfolio_project", owner.UserID); err == nil {
		t.Error("an anonymous caller must be refused")
	}
}

func TestRequireRoleAndPermission(t *testing.T) {
	dev := ident(RoleDeveloper)

	if err := RequireRole(dev, RoleDeveloper, RoleClient); err != nil {
		t.Errorf("a developer must satisfy a developer-or-client requirement: %v", err)
	}
	if err := RequireRole(dev, RoleAdmin); err == nil {
		t.Error("a developer must not satisfy an admin requirement")
	}
	if err := RequirePermission(dev, PermProposalSubmit); err != nil {
		t.Errorf("a developer must satisfy proposal.submit: %v", err)
	}
	if err := RequirePermission(dev, PermPaymentRelease); err == nil {
		t.Error("a developer must not satisfy payment.release")
	}

	// A denial carries a reason for the audit log.
	err := RequirePermission(dev, PermPaymentRelease)
	var d *Denial
	if !asDenial(err, &d) {
		t.Fatalf("RequirePermission returned %T, want *Denial", err)
	}
	if d.Reason == "" {
		t.Error("a denial must record why it refused")
	}
}

func asDenial(err error, target **Denial) bool {
	d, ok := err.(*Denial)
	if ok {
		*target = d
	}
	return ok
}

func TestOwnsRejectsNilIDs(t *testing.T) {
	id := ident(RoleDeveloper)
	if id.Owns(uuid.Nil) {
		t.Error("Owns must never be true for a nil owner id")
	}
	if id.Owns(uuid.New()) {
		t.Error("Owns must be false for someone else's id")
	}
	if !id.Owns(id.UserID) {
		t.Error("Owns must be true for the caller's own id")
	}
}

// Every permission constant must appear in at least one role, or it is dead
// code pretending to be a control.
func TestEveryPermissionIsGrantedToSomeone(t *testing.T) {
	all := []Permission{
		PermProjectCreate, PermProjectManage, PermProposalReview, PermDeveloperInvite,
		PermMilestoneFund, PermMilestoneReview, PermSaveDeveloper, PermProposalSubmit,
		PermPortfolioManage, PermServiceManage, PermGitHubConnect, PermMilestoneSubmit,
		PermSaveProject, PermMessageSend, PermFileUpload, PermReviewWrite,
		PermDisputeOpen, PermProfileManage, PermModerationQueue, PermModerationDecide,
		PermReportReview, PermContentHide, PermUserManage, PermRoleGrant,
		PermPaymentManage, PermPaymentRelease, PermDisputeResolve, PermSettingsManage,
		PermAuditRead, PermAdminDashboard, PermMatchingConfigure,
	}
	for _, p := range all {
		granted := false
		for role := range rolePermissions {
			if _, ok := rolePermissions[role][p]; ok {
				granted = true
				break
			}
		}
		if !granted {
			t.Errorf("permission %s is defined but granted to no role", p)
		}
	}
}
