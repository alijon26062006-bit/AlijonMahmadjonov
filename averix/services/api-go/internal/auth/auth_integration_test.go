package auth_test

import (
	"net/http"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

func TestRegisterCreatesAccountRoleAndProfile(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()

	res := c.Register("ali@example.test", "ali", "fervent-harbour-9218",
		"Ali Mahmadjonov", "developer").OK(t, http.StatusCreated)

	if !res.Bool("authenticated") {
		t.Error("registration must leave the caller signed in")
	}
	if res.String("active_role") != "developer" {
		t.Errorf("active_role = %q, want developer", res.String("active_role"))
	}
	if !res.Bool("is_new") {
		t.Error("is_new must be set so the web app routes into onboarding")
	}
	if res.String("csrf_token") == "" {
		t.Error("a CSRF token must be issued with the session")
	}
	if res.Bool("email_verified") {
		t.Error("a new account must not start with a verified email address")
	}

	userID := res.String("user_id")
	// The role row and the developer profile must exist, or the developer
	// interface has nothing to read.
	if n := h.Count(`SELECT count(*) FROM user_roles WHERE user_id = $1 AND role = 'developer'`, userID); n != 1 {
		t.Errorf("developer role rows = %d, want 1", n)
	}
	if n := h.Count(`SELECT count(*) FROM developer_profiles WHERE user_id = $1`, userID); n != 1 {
		t.Errorf("developer_profiles rows = %d, want 1", n)
	}
	if n := h.Count(`SELECT count(*) FROM client_profiles WHERE user_id = $1`, userID); n != 0 {
		t.Errorf("a developer must not get a client profile (got %d)", n)
	}
	// A profile with nothing in it must not be discoverable.
	var searchable bool
	h.QueryRow([]any{&searchable},
		`SELECT is_searchable FROM developer_profiles WHERE user_id = $1`, userID)
	if searchable {
		t.Error("a developer must not be searchable before onboarding completes")
	}
}

func TestRegisterRejectsBadInput(t *testing.T) {
	h := testsupport.New(t)

	cases := []struct {
		name  string
		body  map[string]any
		field string
	}{
		{"missing email", map[string]any{"username": "x1", "password": "quiet-lantern-4417", "full_name": "X", "role": "client", "accept_terms": true}, "email"},
		{"invalid email", map[string]any{"email": "not-an-email", "username": "x2", "password": "quiet-lantern-4417", "full_name": "X", "role": "client", "accept_terms": true}, "email"},
		{"short password", map[string]any{"email": "a@example.test", "username": "x3", "password": "short", "full_name": "X", "role": "client", "accept_terms": true}, "password"},
		{"common password", map[string]any{"email": "b@example.test", "username": "x4", "password": "password123", "full_name": "X", "role": "client", "accept_terms": true}, "password"},
		{"repetitive password", map[string]any{"email": "c@example.test", "username": "x5", "password": "aaaaaaaaaaaaaa", "full_name": "X", "role": "client", "accept_terms": true}, "password"},
		{"reserved username", map[string]any{"email": "d@example.test", "username": "admin", "password": "quiet-lantern-4417", "full_name": "X", "role": "client", "accept_terms": true}, "username"},
		{"username with spaces", map[string]any{"email": "e@example.test", "username": "not valid", "password": "quiet-lantern-4417", "full_name": "X", "role": "client", "accept_terms": true}, "username"},
		{"no role", map[string]any{"email": "f@example.test", "username": "x6", "password": "quiet-lantern-4417", "full_name": "X", "accept_terms": true}, "role"},
		{"terms not accepted", map[string]any{"email": "g@example.test", "username": "x7", "password": "quiet-lantern-4417", "full_name": "X", "role": "client"}, "accept_terms"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			res := h.Client().POST("/auth/register", tc.body).
				Fails(t, http.StatusUnprocessableEntity, "validation_failed")
			if _, ok := res.Fields[tc.field]; !ok {
				t.Errorf("expected a problem on %q, got %v", tc.field, res.Fields)
			}
		})
	}
}

// A password containing the username or email local part is trivially guessable
// on a product where both are public.
func TestRegisterRejectsPasswordDerivedFromIdentity(t *testing.T) {
	h := testsupport.New(t)

	res := h.Client().POST("/auth/register", map[string]any{
		"email": "sardor@example.test", "username": "sardordev",
		"password": "my-sardordev-key", "full_name": "Sardor", "role": "developer",
		"accept_terms": true,
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if _, ok := res.Fields["password"]; !ok {
		t.Errorf("expected the password to be refused for containing the username, got %v", res.Fields)
	}
}

func TestRegisterRefusesSelfServiceAdminRole(t *testing.T) {
	h := testsupport.New(t)
	// The admin role has no self-service route at all; asking for it is a
	// validation failure, not a silent downgrade to client.
	h.Client().POST("/auth/register", map[string]any{
		"email": "sneaky@example.test", "username": "sneaky",
		"password": "quiet-lantern-4417", "full_name": "Sneaky",
		"role": "admin", "accept_terms": true,
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	if n := h.Count(`SELECT count(*) FROM user_roles WHERE role = 'admin'`); n != 0 {
		t.Errorf("admin role rows = %d, want 0", n)
	}
}

// Over-posting: an unknown field must be refused rather than ignored, so a
// request that tries to set something the endpoint does not accept fails loudly.
func TestRegisterRejectsUnknownFields(t *testing.T) {
	h := testsupport.New(t)
	h.Client().POST("/auth/register", map[string]any{
		"email": "over@example.test", "username": "overpost",
		"password": "quiet-lantern-4417", "full_name": "Over Post",
		"role": "client", "accept_terms": true,
		"status": "active", "identity_verified_at": "2026-01-01T00:00:00Z",
	}).Fails(t, http.StatusBadRequest, "bad_request")
}

func TestDuplicateEmailAndUsernameAreRejected(t *testing.T) {
	h := testsupport.New(t)
	h.Client().RegisterDeveloper("firstuser")

	h.Client().Register("firstuser@example.test", "seconduser", "quiet-lantern-4417",
		"Second", "client").Fails(t, http.StatusConflict, "email_taken")

	h.Client().Register("other@example.test", "firstuser", "quiet-lantern-4417",
		"Other", "client").Fails(t, http.StatusConflict, "username_taken")

	if n := h.Count(`SELECT count(*) FROM users`); n != 1 {
		t.Errorf("users = %d, want 1", n)
	}
}

func TestLoginAndSession(t *testing.T) {
	h := testsupport.New(t)
	h.Client().RegisterClient("buyer")

	c := h.Client()
	if c.Session().Bool("authenticated") {
		t.Error("a fresh client must start anonymous")
	}

	res := c.Login("buyer@example.test", "quiet-lantern-4417").OK(t, http.StatusOK)
	if res.String("active_role") != "client" {
		t.Errorf("active_role = %q, want client", res.String("active_role"))
	}

	session := c.Session().OK(t, http.StatusOK)
	if !session.Bool("authenticated") {
		t.Error("the session cookie must authenticate subsequent requests")
	}
	if session.String("username") != "buyer" {
		t.Errorf("username = %q, want buyer", session.String("username"))
	}
}

func TestLoginRejectsWrongPasswordAndUnknownAccountIdentically(t *testing.T) {
	h := testsupport.New(t)
	h.Client().RegisterClient("realuser")

	wrong := h.Client().Login("realuser@example.test", "not-the-password-99").
		Fails(t, http.StatusUnauthorized, "invalid_credentials")
	unknown := h.Client().Login("ghost@example.test", "not-the-password-99").
		Fails(t, http.StatusUnauthorized, "invalid_credentials")

	// Identical code and message, so the response cannot be used to discover
	// which addresses have accounts.
	if wrong.Message != unknown.Message {
		t.Errorf("a wrong password and an unknown account must be indistinguishable:\n  %q\n  %q",
			wrong.Message, unknown.Message)
	}
}

func TestRepeatedFailuresLockTheAccount(t *testing.T) {
	h := testsupport.New(t)
	h.Client().RegisterClient("locktarget")

	// MAX_FAILED_LOGINS defaults to 8.
	var locked bool
	for i := 0; i < 8; i++ {
		res := h.Client().Login("locktarget@example.test", "wrong-guess-000")
		if res.Status == http.StatusTooManyRequests && res.Code == "account_locked" {
			locked = true
			break
		}
	}
	if !locked {
		t.Fatal("the account was never locked after 8 failed attempts")
	}

	// The correct password must not unlock it: that is the whole point.
	res := h.Client().Login("locktarget@example.test", "quiet-lantern-4417").
		Fails(t, http.StatusTooManyRequests, "account_locked")
	if res.Header.Get("Retry-After") == "" {
		t.Error("a lockout must tell the client when to try again")
	}

	// The lockout is durable, not cache-resident.
	var count int
	h.QueryRow([]any{&count},
		`SELECT failed_login_count FROM users WHERE email = 'locktarget@example.test'`)
	if count < 8 {
		t.Errorf("failed_login_count = %d, want at least 8 recorded in the database", count)
	}
}

func TestSuccessfulLoginClearsTheFailureCount(t *testing.T) {
	h := testsupport.New(t)
	h.Client().RegisterClient("recovering")

	for i := 0; i < 3; i++ {
		h.Client().Login("recovering@example.test", "wrong-guess-000")
	}
	h.Client().Login("recovering@example.test", "quiet-lantern-4417").OK(t, http.StatusOK)

	var count int
	h.QueryRow([]any{&count},
		`SELECT failed_login_count FROM users WHERE email = 'recovering@example.test'`)
	if count != 0 {
		t.Errorf("failed_login_count = %d after a successful sign-in, want 0", count)
	}
}

func TestCSRFIsRequiredForMutations(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("csrfdev")

	// No token.
	c.SuppressCSRF = true
	c.POST("/auth/role/add", map[string]any{"role": "client"}).
		Fails(t, http.StatusForbidden, "csrf_failed")
	c.SuppressCSRF = false

	// Wrong token.
	c.OverrideCSRF = "a-token-from-somewhere-else"
	c.POST("/auth/role/add", map[string]any{"role": "client"}).
		Fails(t, http.StatusForbidden, "csrf_failed")
	c.OverrideCSRF = ""

	// Correct token.
	c.POST("/auth/role/add", map[string]any{"role": "client"}).OK(t, http.StatusOK)

	// A safe method never needs one.
	c.SuppressCSRF = true
	c.Session().OK(t, http.StatusOK)
}

func TestRoleSwitchingKeepsInterfacesSeparate(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("dualrole")

	c.POST("/auth/role/add", map[string]any{"role": "client"}).OK(t, http.StatusOK)

	before := c.CSRF()
	res := c.POST("/auth/role/switch", map[string]any{"role": "client"}).OK(t, http.StatusOK)

	if res.String("active_role") != "client" {
		t.Errorf("active_role = %q, want client", res.String("active_role"))
	}
	if res.CSRFTokenChanged(before) == false {
		t.Error("switching roles must rotate the CSRF token so a form from the previous role cannot be replayed")
	}
	if !res.Has("permissions", "project.create") {
		t.Error("the client interface must grant project.create")
	}
	if res.Has("permissions", "proposal.submit") {
		t.Error("developer capabilities must not leak into the client interface")
	}
	if len(res.Strings("roles")) != 2 {
		t.Errorf("roles = %v, want both roles listed for the switcher", res.Strings("roles"))
	}
}

func TestSwitchingToARoleNotHeldIsRefused(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("onlydev")

	c.POST("/auth/role/switch", map[string]any{"role": "admin"}).
		Fails(t, http.StatusForbidden, "forbidden")
	c.POST("/auth/role/switch", map[string]any{"role": "client"}).
		Fails(t, http.StatusForbidden, "forbidden")

	if c.Session().String("active_role") != "developer" {
		t.Error("a refused switch must leave the active role unchanged")
	}
}

func TestAddRoleOnlyAllowsClientAndDeveloper(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("escalate")

	for _, role := range []string{"admin", "moderator", "superuser"} {
		c.POST("/auth/role/add", map[string]any{"role": role}).
			Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	}
	if n := h.Count(`SELECT count(*) FROM user_roles WHERE role IN ('admin','moderator')`); n != 0 {
		t.Errorf("privileged role rows = %d, want 0", n)
	}
}

func TestLogoutRevokesTheSession(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterClient("leaving")

	c.Logout().OK(t, http.StatusOK)
	if c.Session().Bool("authenticated") {
		t.Error("the session must not authenticate after signing out")
	}
	if n := h.Count(`SELECT count(*) FROM sessions WHERE revoked_at IS NOT NULL`); n != 1 {
		t.Errorf("revoked sessions = %d, want 1", n)
	}
}

func TestLogoutEverywhereEndsOtherDevices(t *testing.T) {
	h := testsupport.New(t)
	first := h.Client()
	first.RegisterClient("multidevice")

	second := h.Client()
	second.Login("multidevice@example.test", "quiet-lantern-4417").OK(t, http.StatusOK)
	if !second.Session().Bool("authenticated") {
		t.Fatal("the second device should be signed in")
	}

	first.POST("/auth/logout-everywhere", nil).OK(t, http.StatusOK)

	if second.Session().Bool("authenticated") {
		t.Error("the other device must be signed out")
	}
	if first.Session().Bool("authenticated") {
		t.Error("the calling device must be signed out too")
	}
}

func TestPasswordChangeRequiresTheCurrentPassword(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterClient("changer")

	res := c.POST("/auth/password/change", map[string]any{
		"current_password": "not-the-current-one",
		"new_password":     "another-good-password-7",
	}).Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	if _, ok := res.Fields["current_password"]; !ok {
		t.Errorf("expected a problem on current_password, got %v", res.Fields)
	}

	c.POST("/auth/password/change", map[string]any{
		"current_password": "quiet-lantern-4417",
		"new_password":     "another-good-password-7",
	}).OK(t, http.StatusOK)

	h.Client().Login("changer@example.test", "quiet-lantern-4417").
		Fails(t, http.StatusUnauthorized, "invalid_credentials")
	h.Client().Login("changer@example.test", "another-good-password-7").OK(t, http.StatusOK)
}

// Changing a password signs out other devices but not the one making the
// change, so the user is not ejected from the page they are on.
func TestPasswordChangeKeepsTheCurrentSessionAndEndsOthers(t *testing.T) {
	h := testsupport.New(t)
	here := h.Client()
	here.RegisterClient("staysignedin")

	elsewhere := h.Client()
	elsewhere.Login("staysignedin@example.test", "quiet-lantern-4417").OK(t, http.StatusOK)

	here.POST("/auth/password/change", map[string]any{
		"current_password": "quiet-lantern-4417",
		"new_password":     "brand-new-passphrase-31",
	}).OK(t, http.StatusOK)

	if !here.Session().Bool("authenticated") {
		t.Error("the session that changed the password must stay signed in")
	}
	if elsewhere.Session().Bool("authenticated") {
		t.Error("other sessions must be signed out after a password change")
	}
}

func TestForgotPasswordNeverRevealsAccountExistence(t *testing.T) {
	h := testsupport.New(t)
	h.Client().RegisterClient("known")

	known := h.Client().POST("/auth/password/forgot",
		map[string]any{"email": "known@example.test"}).OK(t, http.StatusOK)
	unknown := h.Client().POST("/auth/password/forgot",
		map[string]any{"email": "nobody@example.test"}).OK(t, http.StatusOK)

	if known.String("message") != unknown.String("message") {
		t.Errorf("the responses differ and can be used to enumerate accounts:\n  %q\n  %q",
			known.String("message"), unknown.String("message"))
	}
	// A token exists only for the real account.
	if n := h.Count(`SELECT count(*) FROM auth_tokens WHERE purpose = 'password_reset'`); n != 1 {
		t.Errorf("password reset tokens = %d, want exactly 1", n)
	}
}

func TestPasswordResetTokenIsSingleUse(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterClient("resetter")
	c.Logout()

	h.Client().POST("/auth/password/forgot",
		map[string]any{"email": "resetter@example.test"}).OK(t, http.StatusOK)

	// The token is only ever stored hashed, so the test cannot read it back —
	// which is the property being relied on. A known token is planted instead.
	h.Exec(`
		UPDATE auth_tokens
		   SET token_hash = digest('integration-test-reset-token', 'sha256')
		 WHERE purpose = 'password_reset'`)

	h.Client().POST("/auth/password/reset", map[string]any{
		"token": "integration-test-reset-token", "password": "recovered-password-55",
	}).OK(t, http.StatusOK)

	h.Client().Login("resetter@example.test", "recovered-password-55").OK(t, http.StatusOK)

	// Second use of the same link must fail.
	h.Client().POST("/auth/password/reset", map[string]any{
		"token": "integration-test-reset-token", "password": "second-attempt-66",
	}).Fails(t, http.StatusBadRequest, "reset_link_invalid")
}

// A reset revokes every session: if the reset happened because the account was
// compromised, leaving the attacker signed in would defeat it.
func TestPasswordResetRevokesEverySession(t *testing.T) {
	h := testsupport.New(t)
	victim := h.Client()
	victim.RegisterClient("compromised")

	attacker := h.Client()
	attacker.Login("compromised@example.test", "quiet-lantern-4417").OK(t, http.StatusOK)

	h.Client().POST("/auth/password/forgot",
		map[string]any{"email": "compromised@example.test"}).OK(t, http.StatusOK)
	h.Exec(`UPDATE auth_tokens SET token_hash = digest('reset-me-now', 'sha256')
	         WHERE purpose = 'password_reset'`)
	h.Client().POST("/auth/password/reset", map[string]any{
		"token": "reset-me-now", "password": "locked-them-out-88",
	}).OK(t, http.StatusOK)

	if attacker.Session().Bool("authenticated") {
		t.Error("a session held elsewhere must be revoked by a password reset")
	}
	if victim.Session().Bool("authenticated") {
		t.Error("every session must be revoked by a password reset, including the requester's")
	}
}

func TestEmailVerification(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("verifyme")

	if c.Session().Bool("email_verified") {
		t.Fatal("the account should start unverified")
	}
	h.Exec(`UPDATE auth_tokens SET token_hash = digest('verify-this-address', 'sha256')
	         WHERE purpose = 'email_verify'`)

	h.Client().POST("/auth/email/verify",
		map[string]any{"token": "verify-this-address"}).OK(t, http.StatusOK)

	if !c.Session().Bool("email_verified") {
		t.Error("the session must report the address as verified")
	}
	h.Client().POST("/auth/email/verify",
		map[string]any{"token": "verify-this-address"}).
		Fails(t, http.StatusBadRequest, "verification_link_invalid")
}

func TestSessionListingAndRevocation(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterClient("sessionowner")

	other := h.Client()
	other.Login("sessionowner@example.test", "quiet-lantern-4417").OK(t, http.StatusOK)

	res := c.GET("/auth/sessions").OK(t, http.StatusOK)
	if len(res.List) != 2 {
		t.Fatalf("sessions listed = %d, want 2", len(res.List))
	}

	// Find the session that is not the caller's own and revoke it.
	var target string
	for _, raw := range res.List {
		row, _ := raw.(map[string]any)
		if current, _ := row["current"].(bool); !current {
			target, _ = row["id"].(string)
		}
	}
	if target == "" {
		t.Fatal("could not identify the other session")
	}
	c.DELETE("/auth/sessions/"+target).OK(t, http.StatusNoContent)

	if other.Session().Bool("authenticated") {
		t.Error("the revoked session must stop authenticating")
	}
	if !c.Session().Bool("authenticated") {
		t.Error("the caller's own session must be unaffected")
	}
}

// A session id belonging to someone else must not be revocable by guessing it.
func TestCannotRevokeAnotherUsersSession(t *testing.T) {
	h := testsupport.New(t)
	victim := h.Client()
	victim.RegisterClient("victimuser")

	attacker := h.Client()
	attacker.RegisterClient("attackeruser")

	var victimSession string
	h.QueryRow([]any{&victimSession}, `
		SELECT s.id::text FROM sessions s
		JOIN users u ON u.id = s.user_id
		WHERE u.username = 'victimuser' AND s.revoked_at IS NULL`)

	attacker.DELETE("/auth/sessions/"+victimSession).
		Fails(t, http.StatusNotFound, "not_found")

	if !victim.Session().Bool("authenticated") {
		t.Error("the victim's session must survive another user's revocation attempt")
	}
}

// A tampered cookie must not authenticate, and the session it names must be
// revoked rather than left usable.
func TestTamperedSessionCookieIsRejected(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterClient("cookieowner")

	var selector string
	h.QueryRow([]any{&selector}, `
		SELECT s.selector FROM sessions s
		JOIN users u ON u.id = s.user_id
		WHERE u.username = 'cookieowner' AND s.revoked_at IS NULL`)

	forged := h.Client()
	forged.SetRawSessionCookie(selector + ".this-is-not-the-verifier")
	if forged.Session().Bool("authenticated") {
		t.Fatal("a cookie with a wrong verifier must not authenticate")
	}

	// The genuine holder is signed out too: a valid selector with a wrong
	// verifier means the cookie leaked or is being replayed.
	if c.Session().Bool("authenticated") {
		t.Error("the session must be revoked after a verifier mismatch")
	}
}

func TestSuspendedAccountCannotUseItsSession(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("tobesuspended")

	if !c.Session().Bool("authenticated") {
		t.Fatal("should start signed in")
	}
	h.Exec(`UPDATE users SET status = 'suspended', suspended_reason = 'test'
	         WHERE username = 'tobesuspended'`)

	if c.Session().Bool("authenticated") {
		t.Error("a suspension must take effect immediately, not at cookie expiry")
	}
	res := h.Client().Login("tobesuspended@example.test", "quiet-lantern-4417")
	res.Fails(t, http.StatusForbidden, "account_suspended")
}

// Revoking a role must invalidate a session that was operating in it.
func TestRevokedRoleInvalidatesTheSession(t *testing.T) {
	h := testsupport.New(t)
	c := h.Client()
	c.RegisterDeveloper("loserole")

	h.Exec(`DELETE FROM user_roles WHERE role = 'developer'
	         AND user_id = (SELECT id FROM users WHERE username = 'loserole')`)

	if c.Session().Bool("authenticated") {
		t.Error("a session in a role the account no longer holds must stop working")
	}
}

func TestAvailabilityEndpoint(t *testing.T) {
	h := testsupport.New(t)
	h.Client().RegisterDeveloper("existinguser")

	cases := []struct {
		field, value string
		available    bool
	}{
		{"username", "existinguser", false},
		{"username", "freshname", true},
		{"username", "admin", false},
		{"username", "ab", false},
		{"email", "existinguser@example.test", false},
		{"email", "brand-new@example.test", true},
		{"email", "nonsense", false},
	}
	for _, tc := range cases {
		res := h.Client().GET("/auth/availability?field="+tc.field+"&value="+tc.value).
			OK(t, http.StatusOK)
		if got := res.Bool("available"); got != tc.available {
			t.Errorf("%s=%q available = %v, want %v (reason: %q)",
				tc.field, tc.value, got, tc.available, res.String("reason"))
		}
	}
	h.Client().GET("/auth/availability?field=password&value=x").
		Fails(t, http.StatusBadRequest, "bad_request")
}

// An internal failure must never reach the client as a database message.
func TestErrorResponsesCarryARequestIDAndNoInternals(t *testing.T) {
	h := testsupport.New(t)
	res := h.Client().Login("nobody@example.test", "wrong-password-11").
		Fails(t, http.StatusUnauthorized, "invalid_credentials")

	if res.RequestID == "" {
		t.Error("an error response must carry a request id so it can be traced")
	}
	if res.Header.Get("X-Request-Id") == "" {
		t.Error("every response must carry X-Request-Id")
	}
	for _, leak := range []string{"pgx", "postgres", "SELECT", "sql:", "relation", "goroutine"} {
		if contains(res.Raw, leak) {
			t.Errorf("the error body leaks internals (%q): %s", leak, res.Raw)
		}
	}
}

func TestSecurityHeadersArePresent(t *testing.T) {
	h := testsupport.New(t)
	res := h.Client().Session().OK(t, http.StatusOK)

	want := map[string]string{
		"X-Content-Type-Options": "nosniff",
		"X-Frame-Options":        "DENY",
		"Referrer-Policy":        "strict-origin-when-cross-origin",
		"Cache-Control":          "no-store, private",
	}
	for header, expected := range want {
		if got := res.Header.Get(header); got != expected {
			t.Errorf("%s = %q, want %q", header, got, expected)
		}
	}
	if csp := res.Header.Get("Content-Security-Policy"); csp == "" {
		t.Error("the API must send a Content-Security-Policy")
	}
}

func contains(haystack []byte, needle string) bool {
	return len(needle) > 0 && len(haystack) >= len(needle) &&
		indexOf(string(haystack), needle) >= 0
}

func indexOf(s, sub string) int {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}
