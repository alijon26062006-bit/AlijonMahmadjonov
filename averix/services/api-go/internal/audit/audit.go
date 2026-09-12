// Package audit appends the record of who did what.
//
// Writes here are append-only and deliberately never fail a request: an audit
// write that could block a payment release would be a denial-of-service, so a
// failure is logged loudly instead. The table is the evidence for disputes and
// for answering "which admin looked at this contract".
package audit

import (
	"context"
	"encoding/json"
	"net"

	"github.com/google/uuid"

	"github.com/averix/api/internal/platform/database"
	"github.com/averix/api/internal/platform/httpx"
	"github.com/averix/api/internal/platform/logx"
	"github.com/averix/api/internal/security"
)

// Actions are named "<subject>.<verb>" so the admin panel can group them and a
// query for everything that touched money is one prefix match.
const (
	ActionLogin           = "auth.login"
	ActionLoginFailed     = "auth.login_failed"
	ActionLogout          = "auth.logout"
	ActionRegister        = "auth.register"
	ActionPasswordReset   = "auth.password_reset"
	ActionPasswordChanged = "auth.password_changed"
	ActionSessionRevoked  = "auth.session_revoked"
	ActionRoleSwitched    = "auth.role_switched"
	ActionEmailVerified   = "auth.email_verified"

	ActionGitHubConnected      = "github.connected"
	ActionGitHubDisconnected   = "github.disconnected"
	ActionGitHubPrivateGranted = "github.private_access_granted"

	ActionProjectPublished      = "project.published"
	ActionProjectCancelled      = "project.cancelled"
	ActionProposalAccepted      = "proposal.accepted"
	ActionContractCreated       = "contract.created"
	ActionContractViewedByAdmin = "contract.viewed_by_admin"
	ActionMilestoneApproved     = "milestone.approved"
	ActionMilestoneReleased     = "milestone.released"

	ActionPaymentCreated  = "payment.created"
	ActionPaymentReleased = "payment.released"
	ActionPaymentRefunded = "payment.refunded"
	ActionWebhookRejected = "payment.webhook_rejected"

	ActionUserSuspended    = "user.suspended"
	ActionUserUnsuspended  = "user.unsuspended"
	ActionUserWarned       = "user.warned"
	ActionRoleGranted      = "user.role_granted"
	ActionRoleRevoked      = "user.role_revoked"
	ActionIdentityVerified = "user.identity_verified"

	ActionContentHidden   = "moderation.content_hidden"
	ActionContentRestored = "moderation.content_restored"
	ActionReportResolved  = "moderation.report_resolved"
	ActionDisputeResolved = "dispute.resolved"

	ActionSettingChanged         = "settings.changed"
	ActionFeatureFlagChanged     = "settings.feature_flag_changed"
	ActionMatchingWeightsChanged = "settings.matching_weights_changed"

	ActionAccessDenied = "security.access_denied"
	ActionRateLimited  = "security.rate_limited"
)

type Outcome string

const (
	Success Outcome = "success"
	Denied  Outcome = "denied"
	Failure Outcome = "error"
)

// Entry is one audit record.
type Entry struct {
	ActorID     *uuid.UUID
	ActorRole   string
	Action      string
	SubjectType string
	SubjectID   *uuid.UUID
	Before      any
	After       any
	IP          string
	UserAgent   string
	RequestID   string
	Outcome     Outcome
	Detail      string
}

type Recorder struct {
	db *database.DB
}

func New(db *database.DB) *Recorder { return &Recorder{db: db} }

// Record appends an entry. Errors are logged, not returned: see the package
// comment for why.
func (r *Recorder) Record(ctx context.Context, e Entry) {
	if r == nil || r.db == nil {
		return
	}
	if e.Outcome == "" {
		e.Outcome = Success
	}
	if e.RequestID == "" {
		e.RequestID = logx.RequestID(ctx)
	}

	before, err := marshalOrNil(e.Before)
	if err != nil {
		logx.From(ctx).Error("audit: could not encode before state", "action", e.Action, "error", err)
	}
	after, err := marshalOrNil(e.After)
	if err != nil {
		logx.From(ctx).Error("audit: could not encode after state", "action", e.Action, "error", err)
	}

	var ip any
	if e.IP != "" {
		if parsed := net.ParseIP(e.IP); parsed != nil {
			ip = parsed.String()
		}
	}

	// The audit write uses a context detached from the request's cancellation:
	// a client that hangs up after triggering a payment release must not erase
	// the record of it.
	writeCtx := context.WithoutCancel(ctx)
	_, err = r.db.Exec(writeCtx, `
		INSERT INTO audit_logs
		  (actor_id, actor_role, action, subject_type, subject_id,
		   before, after, ip, user_agent, request_id, outcome, detail)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)`,
		e.ActorID, nullIfEmpty(e.ActorRole), e.Action, nullIfEmpty(e.SubjectType), e.SubjectID,
		before, after, ip, truncate(e.UserAgent, 400), nullIfEmpty(e.RequestID),
		string(e.Outcome), nullIfEmpty(e.Detail))
	if err != nil {
		logx.From(ctx).Error("audit: could not write entry",
			"action", e.Action, "subject_type", e.SubjectType, "error", err)
	}
}

// FromRequest fills the actor, address and user agent from the request context.
func (r *Recorder) FromRequest(ctx context.Context, e Entry) Entry {
	if id := security.FromContext(ctx); id.Authenticated() {
		actor := id.UserID
		e.ActorID = &actor
		if e.ActorRole == "" {
			e.ActorRole = string(id.ActiveRole)
		}
	}
	if e.IP == "" {
		e.IP = httpx.ClientIP(ctx)
	}
	return e
}

// RecordRequest is the common path: take the actor from the context and append.
func (r *Recorder) RecordRequest(ctx context.Context, e Entry) {
	r.Record(ctx, r.FromRequest(ctx, e))
}

// Denial records a refused authorisation check. Every 403 the product returns
// leaves one of these, which is what makes a probing attempt visible.
func (r *Recorder) Denial(ctx context.Context, subjectType string, subjectID *uuid.UUID, reason string) {
	r.RecordRequest(ctx, Entry{
		Action:      ActionAccessDenied,
		SubjectType: subjectType,
		SubjectID:   subjectID,
		Outcome:     Denied,
		Detail:      reason,
	})
}

func marshalOrNil(v any) (any, error) {
	if v == nil {
		return nil, nil
	}
	raw, err := json.Marshal(v)
	if err != nil {
		return nil, err
	}
	return raw, nil
}

func nullIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func truncate(s string, n int) any {
	if s == "" {
		return nil
	}
	if len(s) > n {
		return s[:n]
	}
	return s
}
