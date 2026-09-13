package identity_test

import (
	"bytes"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"mime/multipart"
	"net/http"
	"net/textproto"
	"testing"

	"github.com/averix/api/internal/platform/testsupport"
)

// The whole point of this package is that a passport photograph is harder to
// reach than anything else in the product. These tests are written from the
// outside, as an attacker would come at it: hold a role, hold a session, hold
// a link — and still be refused.

func TestIdentityDocumentsAreUnreachableWithoutAnExplicitGrant(t *testing.T) {
	h := testsupport.New(t)
	admin := h.NewAdmin("operator")
	person := newApplicant(h, "applicant")

	// A person submits.
	submitVerification(t, h, person.Client)

	// An administrator — the most powerful role the product has — cannot open
	// the section at all until the permission is granted by name.
	admin.Client.GET("/admin/identity/queue").Fails(t, http.StatusForbidden, "forbidden")
	admin.Client.GET("/admin/identity/users/"+person.UserID).Fails(t, http.StatusForbidden, "forbidden")

	// Granting it is itself an administrator's act, and it is recorded.
	admin.Client.POST("/admin/users/"+admin.UserID+"/permissions", map[string]any{
		"permission": "identity_verification.view",
		"note":       "разбирает очередь проверок",
	}).OK(t, http.StatusOK)
	admin.Client.POST("/admin/users/"+admin.UserID+"/permissions", map[string]any{
		"permission": "identity_verification.review",
	}).OK(t, http.StatusOK)
	if h.Count(`SELECT count(*) FROM audit_logs WHERE action = 'permission.granted'`) != 2 {
		t.Error("granting a permission must leave an audit entry")
	}

	// Even with the permission, the section stays shut until the password is
	// re-entered: a session left open on a desk is not authorisation.
	admin.Client.GET("/admin/identity/queue").Fails(t, http.StatusForbidden, "identity_locked")

	admin.Client.POST("/admin/identity/unlock", map[string]any{"password": "wrong-password-entirely"}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")
	admin.Client.POST("/admin/identity/unlock", map[string]any{"password": testsupport.Password}).
		OK(t, http.StatusOK)

	queue := admin.Client.GET("/admin/identity/queue").OK(t, http.StatusOK)
	if len(queue.List) != 1 {
		t.Fatalf("queue = %d, want the submitted case: %s", len(queue.List), queue.Raw)
	}
	item := queue.List[0].(map[string]any)
	if item["username"] != "applicant" || item["documents"] != float64(2) {
		t.Errorf("queue item = %v", item)
	}

	// A permission that is taken away stops working immediately.
	admin.Client.DELETE("/admin/users/"+admin.UserID+"/permissions/identity_verification.view").
		OK(t, http.StatusOK)
	admin.Client.GET("/admin/identity/queue").Fails(t, http.StatusForbidden, "forbidden")
}

func TestReviewerSeesDocumentsOnlyThroughAShortLivedTicket(t *testing.T) {
	h := testsupport.New(t)
	admin := h.NewAdmin("reviewer")
	person := newApplicant(h, "applicant")
	submitVerification(t, h, person.Client)
	unlockedReviewer(t, h, admin)

	view := admin.Client.GET("/admin/identity/users/"+person.UserID).OK(t, http.StatusOK)
	documents, _ := view.Data["documents"].([]any)
	if len(documents) != 2 {
		t.Fatalf("documents = %d, want front and selfie: %s", len(documents), view.Raw)
	}
	front := documents[0].(map[string]any)
	docID := front["id"].(string)

	// Opening the case is already an access worth recording.
	if h.Count(`SELECT count(*) FROM admin_access_logs WHERE action = 'open'`) != 1 {
		t.Error("opening a case must be written to the access log")
	}

	// No URL anywhere in the response: the reviewer has to ask for a ticket.
	if bytes.Contains([]byte(view.Raw), []byte("storage_key")) ||
		bytes.Contains([]byte(view.Raw), []byte("http")) {
		t.Errorf("a case must not carry any address for its images: %s", view.Raw)
	}

	// The image endpoint refuses a request without one.
	admin.Client.GET("/admin/identity/documents/"+docID+"/file").
		Fails(t, http.StatusForbidden, "forbidden")

	ticket := admin.Client.POST("/admin/identity/documents/"+docID+"/token",
		map[string]any{"reason": "проверка соответствия имени"}).OK(t, http.StatusCreated)
	token := ticket.String("token")
	if token == "" {
		t.Fatalf("no token issued: %s", ticket.Raw)
	}

	// Issuing it is logged with the reason the reviewer gave.
	var reason string
	h.QueryRow([]any{&reason},
		`SELECT reason FROM admin_access_logs WHERE action LIKE 'view:%' ORDER BY created_at DESC LIMIT 1`)
	if reason != "проверка соответствия имени" {
		t.Errorf("access reason = %q, want the reviewer's own words", reason)
	}

	// The ticket works for this reviewer…
	image := admin.Client.Fetch("/admin/identity/documents/" + docID + "/file?t=" + token)
	if image.Status != http.StatusOK {
		t.Fatalf("image status = %d, want 200", image.Status)
	}
	if cache := image.Header.Get("Cache-Control"); cache != "no-store, no-cache, must-revalidate, private" {
		t.Errorf("Cache-Control = %q; a passport must not be cached anywhere", cache)
	}

	if !bytes.HasPrefix(image.Raw, []byte("\x89PNG")) {
		t.Errorf("the image endpoint must answer with the image itself, got %d bytes", len(image.Raw))
	}

	// …and for nobody else, even another reviewer with the same rights and a
	// ticket of their own for the same document.
	second := h.NewAdmin("second")
	unlockedReviewer(t, h, second)
	second.Client.GET("/admin/identity/documents/"+docID+"/file?t="+token).
		Fails(t, http.StatusForbidden, "forbidden")
	theirs := second.Client.POST("/admin/identity/documents/"+docID+"/token",
		map[string]any{"reason": "вторая пара глаз"}).OK(t, http.StatusCreated)
	admin.Client.GET("/admin/identity/documents/"+docID+"/file?t="+theirs.String("token")).
		Fails(t, http.StatusForbidden, "forbidden")
}

func TestOwnerSeesTheirOwnCaseAndNobodyElsesDocuments(t *testing.T) {
	h := testsupport.New(t)
	person := newApplicant(h, "applicant")
	other := newApplicant(h, "stranger")
	submitVerification(t, h, person.Client)

	mine := person.Client.GET("/account/identity").OK(t, http.StatusOK)
	if mine.String("status") != "submitted" {
		t.Errorf("status = %q, want submitted: %s", mine.String("status"), mine.Raw)
	}
	documents, _ := mine.Data["documents"].([]any)
	if len(documents) != 2 {
		t.Errorf("the owner sees their own documents listed, got %d", len(documents))
	}
	docID := documents[0].(map[string]any)["id"].(string)

	// A person cannot reach the reviewer's endpoints, not even for their own
	// documents: those routes are for staff, and the image is served only
	// against a ticket staff can obtain.
	person.Client.GET("/admin/identity/documents/"+docID+"/file").Fails(t, http.StatusForbidden, "")
	other.Client.GET("/admin/identity/users/"+person.UserID).Fails(t, http.StatusForbidden, "")

	// And the case is not visible through the ordinary profile endpoints.
	public := h.Client().GET("/clients/" + "applicant")
	if public.Status == http.StatusOK && bytes.Contains([]byte(public.Raw), []byte("document")) {
		t.Errorf("a public profile must say nothing about documents: %s", public.Raw)
	}
}

func TestDecisionsNotifyThePersonAndLeaveARecord(t *testing.T) {
	h := testsupport.New(t)
	admin := h.NewAdmin("reviewer")
	person := newApplicant(h, "applicant")
	submitVerification(t, h, person.Client)
	unlockedReviewer(t, h, admin)

	view := admin.Client.GET("/admin/identity/users/"+person.UserID).OK(t, http.StatusOK)
	caseID := view.String("id")

	// A decision without an explanation is refused: the next reviewer has to
	// be able to see what this one checked.
	admin.Client.POST("/admin/identity/cases/"+caseID+"/decide", map[string]any{"action": "approve"}).
		Fails(t, http.StatusUnprocessableEntity, "validation_failed")

	// Asking for one photograph again names which one and why.
	admin.Client.POST("/admin/identity/cases/"+caseID+"/decide", map[string]any{
		"action": "request_resubmit", "reason": "Лицевая сторона не читается целиком.",
		"reasons": []string{"cropped"},
	}).OK(t, http.StatusOK)

	again := person.Client.GET("/account/identity").OK(t, http.StatusOK)
	if again.String("status") != "resubmit_requested" {
		t.Errorf("status = %q, want resubmit_requested", again.String("status"))
	}
	resubmit, _ := again.Data["resubmit"].([]any)
	if len(resubmit) != 1 {
		t.Fatalf("the person must be told what to retake: %s", again.Raw)
	}
	if h.Count(`SELECT count(*) FROM notifications WHERE type = 'identity_resubmit_requested'`) != 1 {
		t.Error("a resubmission request must reach the person")
	}
	// Retaking one image does not throw away the rest of the case.
	if documents, _ := again.Data["documents"].([]any); len(documents) != 2 {
		t.Errorf("documents = %d; asking for one photograph must not reset the case", len(documents))
	}

	// The person retakes it and the case is theirs to submit again.
	uploadDocument(t, person.Client, "front", samplePNG(900, 600))
	person.Client.POST("/account/identity/submit", nil).OK(t, http.StatusOK)

	admin.Client.POST("/admin/identity/cases/"+caseID+"/decide", map[string]any{
		"action": "approve", "reason": "Имя и дата рождения совпадают с профилем.",
	}).OK(t, http.StatusOK)

	if h.Count(`SELECT count(*) FROM notifications WHERE type = 'identity_approved'`) != 1 {
		t.Error("an approval must reach the person")
	}
	if h.Count(`SELECT count(*) FROM users WHERE id = '`+person.UserID+`' AND identity_verified_at IS NOT NULL`) != 1 {
		t.Error("an approval must mark the account verified")
	}
	if h.Count(`SELECT count(*) FROM identity_review_actions`) < 3 {
		t.Error("every decision belongs in the case history")
	}

	// Retention was set by the approval: the images do not live forever.
	if h.Count(`SELECT count(*) FROM identity_documents WHERE retention_expires_at IS NULL AND deleted_at IS NULL`) != 0 {
		t.Error("an approved case must give its documents an expiry")
	}

	// The record of who looked is readable, and is itself behind a permission.
	log := admin.Client.GET("/admin/identity/users/"+person.UserID+"/access-log").OK(t, http.StatusOK)
	if len(log.List) == 0 {
		t.Error("the access log must show who opened this person's documents")
	}
}

func TestRetentionRemovesImagesAndKeepsTheDecision(t *testing.T) {
	h := testsupport.New(t)
	admin := h.NewAdmin("reviewer")
	person := newApplicant(h, "applicant")
	submitVerification(t, h, person.Client)
	unlockedReviewer(t, h, admin)

	view := admin.Client.GET("/admin/identity/users/"+person.UserID).OK(t, http.StatusOK)
	admin.Client.POST("/admin/identity/cases/"+view.String("id")+"/decide", map[string]any{
		"action": "approve", "reason": "Документ читается, данные совпадают.",
	}).OK(t, http.StatusOK)

	// Move the retention into the past, as time would.
	h.Exec(`UPDATE identity_documents SET retention_expires_at = now() - interval '1 day'`)
	if _, err := h.App.Identity.PurgeExpired(t.Context()); err != nil {
		t.Fatalf("purge: %v", err)
	}

	if h.Count(`SELECT count(*) FROM identity_documents WHERE deleted_at IS NOT NULL AND storage_key = ''`) != 2 {
		t.Error("expired images must be deleted and their keys cleared")
	}
	var status string
	h.QueryRow([]any{&status}, `SELECT status FROM identity_verifications LIMIT 1`)
	if status != "approved" {
		t.Errorf("the decision must outlive the images, got %q", status)
	}
	if h.Count(`SELECT count(*) FROM users WHERE id = '`+person.UserID+`' AND identity_verified_at IS NOT NULL`) != 1 {
		t.Error("deleting the images must not un-verify the person")
	}
}

// ── Helpers ─────────────────────────────────────────────────────────────────

// newApplicant — тот, кто вообще может подавать документы: исполнитель.
// Проверка снимается сразу после регистрации, потому что PublishDeveloper
// отдаёт уже проверенного, а здесь проверяется сам путь к этому состоянию.
func newApplicant(h *testsupport.Harness, username string) *testsupport.Developer {
	h.T.Helper()
	dev := h.PublishDeveloper(username, "telegram-developer", "python", "telegram-api")
	h.Exec(`UPDATE users SET identity_verified_at = NULL WHERE username = $1`, username)
	return dev
}

func submitVerification(t *testing.T, h *testsupport.Harness, c *testsupport.Client) {
	t.Helper()
	c.POST("/account/identity", map[string]any{
		"document_type": "passport", "country_code": "KZ",
		"document_name": "Ali Example", "date_of_birth": "1996-04-18",
	}).OK(t, http.StatusOK)
	uploadDocument(t, c, "front", samplePNG(900, 600))
	uploadDocument(t, c, "selfie", samplePNG(800, 800))
	c.POST("/account/identity/submit", nil).OK(t, http.StatusOK)
}

func unlockedReviewer(t *testing.T, h *testsupport.Harness, admin *testsupport.Admin) {
	t.Helper()
	for _, permission := range []string{"identity_verification.view", "identity_verification.review"} {
		h.Exec(`INSERT INTO admin_permission_grants (user_id, permission) VALUES ($1::uuid, $2)
		        ON CONFLICT DO NOTHING`, admin.UserID, permission)
	}
	admin.Client.POST("/admin/identity/unlock", map[string]any{"password": testsupport.Password}).
		OK(t, http.StatusOK)
}

func uploadDocument(t *testing.T, c *testsupport.Client, kind string, body []byte) {
	t.Helper()
	var buf bytes.Buffer
	w := multipart.NewWriter(&buf)
	if err := w.WriteField("kind", kind); err != nil {
		t.Fatalf("write field: %v", err)
	}
	headers := textproto.MIMEHeader{}
	headers.Set("Content-Disposition", fmt.Sprintf(`form-data; name="file"; filename=%q`, kind+".png"))
	headers.Set("Content-Type", "image/png")
	part, err := w.CreatePart(headers)
	if err != nil {
		t.Fatalf("create part: %v", err)
	}
	if _, err := part.Write(body); err != nil {
		t.Fatalf("write part: %v", err)
	}
	if err := w.Close(); err != nil {
		t.Fatalf("close writer: %v", err)
	}
	c.Multipart("/account/identity/documents", w.FormDataContentType(), buf.Bytes()).
		OK(t, http.StatusCreated)
}

func samplePNG(width, height int) []byte {
	m := image.NewRGBA(image.Rect(0, 0, width, height))
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			m.Set(x, y, color.RGBA{R: uint8(x % 255), G: uint8(y % 255), B: 90, A: 255})
		}
	}
	var buf bytes.Buffer
	if err := png.Encode(&buf, m); err != nil {
		panic(err)
	}
	return buf.Bytes()
}

// serviceBody — услуга, у которой в порядке все поля: проверяется не форма, а
// доступ к деньгам.
func serviceBody() map[string]any {
	return map[string]any{
		"title":   "Настрою обмен с 1С под ключ",
		"summary": "Выгрузка номенклатуры, остатков и документов в обе стороны.",
		"description": "Настраиваю обмен между 1С и сайтом: справочники, остатки, цены и " +
			"документы. Показываю на тестовой базе, потом переношу в рабочую.",
		"category_slug": "telegram-bots",
		"currency":      "USD",
		"revisions":     2,
		"skills":        []string{"python", "telegram-api"},
		"tiers": []map[string]any{
			{"name": "Базовый", "price_minor": 30000, "delivery_days": 7, "revisions": 1,
				"includes": []string{"Справочники"}},
			{"name": "Полный", "price_minor": 60000, "delivery_days": 14, "revisions": 2,
				"includes": []string{"Справочники", "Документы"}},
		},
	}
}

// proposalBody — отклик, который проходит проверку полей: дело не в них, а в
// том, пускают ли исполнителя вообще.
func proposalBody(projectID string) map[string]any {
	return map[string]any{
		"project_id":    projectID,
		"amount_minor":  150000,
		"currency":      "USD",
		"delivery_days": 14,
		"cover_letter": "Делал такие интеграции трижды, последний раз для оптовой базы " +
			"с обменом номенклатурой и документами. Начну с выгрузки справочников, " +
			"потом двусторонний обмен документами, покажу на тестовой базе.",
		"approach": "Сначала согласуем список объектов обмена и расписание, потом " +
			"выгрузка справочников в одну сторону, приёмка, и только после этого " +
			"документы в обе стороны — так ошибки видно сразу, а не в конце.",
		"relevant_experience": "Шесть лет на бэкенде, из них три — интеграции с учётными " +
			"системами и обменом через файлы и HTTP.",
	}
}

// Верификация принадлежит одной стороне площадки.
//
// Заказчик платит и ничего не получает от площадки деньгами — его паспорт ей
// не нужен, и она его не спрашивает. Проверяется не только то, что кнопки нет
// в интерфейсе: интерфейс можно обойти, а этот отказ — нет.
func TestAClientIsNeverAskedForDocuments(t *testing.T) {
	h := testsupport.New(t)
	client := h.NewClient("buyer")

	for _, call := range []struct {
		name string
		do   func() *testsupport.Response
	}{
		{"своё дело", func() *testsupport.Response { return client.Client.GET("/account/identity") }},
		{"список документов", func() *testsupport.Response { return client.Client.GET("/account/identity/options") }},
		{"начать проверку", func() *testsupport.Response {
			return client.Client.POST("/account/identity", map[string]any{
				"document_type": "passport", "country_code": "RU",
			})
		}},
		{"отправить на проверку", func() *testsupport.Response {
			return client.Client.POST("/account/identity/submit", nil)
		}},
	} {
		call.do().Fails(t, http.StatusForbidden, "identity_not_applicable")
		_ = call.name
	}

	if n := h.Count(`SELECT count(*) FROM identity_verifications`); n != 0 {
		t.Errorf("дел заведено %d, а у заказчика их не бывает", n)
	}
}

// Исполнителю она, наоборот, нужна — и до неё он не может зарабатывать.
func TestAFreelancerWorksOnlyAfterVerification(t *testing.T) {
	h := testsupport.New(t)

	// Профиль заполнен и опубликован: анкета проверки не требует.
	dev := h.PublishDeveloper("unverified", "telegram-developer", "python", "telegram-api")
	h.Exec(`UPDATE users SET identity_verified_at = NULL WHERE username = 'unverified'`)

	client := h.NewClient("hiring")
	projectID := h.PublishProject(client, "Интеграция с 1С", "telegram-bots",
		[]string{"python"}, 100000, 200000)

	// Отклик — первый шаг к оплате, и он закрыт.
	dev.Client.POST("/proposals", proposalBody(projectID)).Fails(t, http.StatusForbidden, "identity_not_verified")

	// Услуга — тоже предложение работы за деньги.
	dev.Client.POST("/services", serviceBody()).Fails(t, http.StatusForbidden, "identity_not_verified")

	// А профиль остаётся своим: заполнять и смотреть можно без документов.
	dev.Client.GET("/developers/me").OK(t, http.StatusOK)

	// Проверка пройдена — и всё то же самое работает.
	h.VerifyIdentity("unverified")
	proposal := dev.Client.POST("/proposals", proposalBody(projectID)).OK(t, http.StatusCreated)

	// И нанять его теперь можно.
	client.Client.POST("/contracts", map[string]any{"proposal_id": proposal.String("id")}).
		OK(t, http.StatusCreated)
}

// Заказчик не может нанять того, кто ещё не подтвердил личность: правило
// живёт на сервере, а не в кнопке, которую ему не показали.
func TestHiringAnUnverifiedFreelancerIsRefused(t *testing.T) {
	h := testsupport.New(t)
	dev := h.PublishDeveloper("pending-check", "telegram-developer", "python", "telegram-api")
	client := h.NewClient("employer")
	projectID := h.PublishProject(client, "Телеграм-бот для записи", "telegram-bots",
		[]string{"python"}, 50000, 90000)

	proposal := dev.Client.POST("/proposals", proposalBody(projectID)).OK(t, http.StatusCreated)

	// Проверка снята уже после отклика — так бывает, если решение отменили.
	h.Exec(`UPDATE users SET identity_verified_at = NULL WHERE username = 'pending-check'`)

	client.Client.POST("/contracts", map[string]any{"proposal_id": proposal.String("id")}).
		Fails(t, http.StatusForbidden, "identity_not_verified")
}

// Требование выключается настройкой — площадке, которой оно не нужно, оно не
// навязывается.
func TestTheRequirementCanBeTurnedOff(t *testing.T) {
	h := testsupport.New(t)
	h.SetSetting("identity.required_for_work", false)

	dev := h.PublishDeveloper("nochecks", "telegram-developer", "python", "telegram-api")
	h.Exec(`UPDATE users SET identity_verified_at = NULL WHERE username = 'nochecks'`)
	client := h.NewClient("relaxed")
	projectID := h.PublishProject(client, "Лендинг для студии", "telegram-bots",
		[]string{"python"}, 30000, 60000)

	dev.Client.POST("/proposals", proposalBody(projectID)).OK(t, http.StatusCreated)
}
