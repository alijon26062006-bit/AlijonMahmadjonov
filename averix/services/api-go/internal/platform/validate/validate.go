// Package validate collects input rules shared across modules.
//
// Validators return field-keyed messages written for the person filling in the
// form, because those messages are what the web app renders under the input.
package validate

import (
	"fmt"
	"net/mail"
	"regexp"
	"strings"
	"unicode"
	"unicode/utf8"
)

// Errors accumulates field problems so a form reports everything at once
// rather than one error per round trip.
type Errors struct {
	fields map[string]string
}

func New() *Errors { return &Errors{fields: map[string]string{}} }

func (e *Errors) Add(field, message string) {
	if _, exists := e.fields[field]; !exists {
		e.fields[field] = message
	}
}

func (e *Errors) Addf(field, format string, args ...any) {
	e.Add(field, fmt.Sprintf(format, args...))
}

func (e *Errors) Any() bool { return len(e.fields) > 0 }

func (e *Errors) Fields() map[string]string { return e.fields }

// ── Strings ─────────────────────────────────────────────────────────────────

// Required trims and reports an empty value.
func (e *Errors) Required(field, label, value string) string {
	v := strings.TrimSpace(value)
	if v == "" {
		e.Addf(field, "«%s» — обязательное поле.", label)
	}
	return v
}

// Length checks a rune count, not a byte count: a Cyrillic bio must not be
// rejected for being "too long" because its characters take two bytes.
func (e *Errors) Length(field, label, value string, min, max int) {
	n := utf8.RuneCountInString(strings.TrimSpace(value))
	switch {
	case n < min && n == 0:
		e.Addf(field, "«%s» — обязательное поле.", label)
	case n < min:
		e.Addf(field, "«%s»: нужно не меньше %d символов (сейчас %d).", label, min, n)
	case max > 0 && n > max:
		e.Addf(field, "«%s»: не больше %d символов (сейчас %d).", label, max, n)
	}
}

// NoControlChars rejects characters that would corrupt rendering or logs.
func (e *Errors) NoControlChars(field, label, value string) {
	for _, r := range value {
		// Zero-width space and BOM are invisible in a form but corrupt search
		// indexes and slugs, so they are refused with the control characters.
		const zeroWidthSpace, byteOrderMark = '\u200b', '\ufeff'
		if r != '\n' && r != '\t' && (unicode.IsControl(r) || r == zeroWidthSpace || r == byteOrderMark) {
			e.Addf(field, "«%s» содержит недопустимые символы.", label)
			return
		}
	}
}

// ── Identity ────────────────────────────────────────────────────────────────

const maxEmailLength = 254

// Email normalises and validates an address.
func (e *Errors) Email(field, value string) string {
	v := strings.ToLower(strings.TrimSpace(value))
	if v == "" {
		e.Add(field, "Укажите адрес электронной почты.")
		return ""
	}
	if len(v) > maxEmailLength {
		e.Add(field, "Этот адрес слишком длинный.")
		return v
	}
	addr, err := mail.ParseAddress(v)
	if err != nil || addr.Address != v || !strings.Contains(v, ".") {
		e.Add(field, "Проверьте адрес: похоже, в нём опечатка.")
		return v
	}
	// A display name would smuggle a second address past the parser.
	if addr.Name != "" {
		e.Add(field, "Укажите только адрес, без имени перед ним.")
	}
	return addr.Address
}

// Matches the CHECK constraint on users.username, so a value that passes here
// cannot be rejected by the database.
var usernamePattern = regexp.MustCompile(`^[a-z0-9][a-z0-9_-]{1,28}[a-z0-9]$`)

// Words that must not become a username, because a profile at /alijon is
// indistinguishable from a route at /admin.
var reservedUsernames = map[string]struct{}{
	"admin": {}, "administrator": {}, "averix": {}, "api": {}, "app": {},
	"auth": {}, "login": {}, "logout": {}, "register": {}, "signup": {},
	"signin": {}, "settings": {}, "account": {}, "billing": {}, "payments": {},
	"support": {}, "help": {}, "about": {}, "legal": {}, "terms": {},
	"privacy": {}, "security": {}, "status": {}, "health": {}, "ready": {},
	"static": {}, "assets": {}, "public": {}, "media": {}, "files": {},
	"upload": {}, "uploads": {}, "download": {}, "search": {}, "explore": {},
	"projects": {}, "project": {}, "developers": {}, "developer": {},
	"clients": {}, "client": {}, "proposals": {}, "contracts": {},
	"milestones": {}, "messages": {}, "notifications": {}, "portfolio": {},
	"services": {}, "reviews": {}, "github": {}, "webhook": {}, "webhooks": {},
	"me": {}, "you": {}, "system": {}, "root": {}, "null": {}, "undefined": {},
	"moderator": {}, "mod": {}, "staff": {}, "team": {}, "official": {},
}

// Username normalises and validates a handle.
func (e *Errors) Username(field, value string) string {
	v := strings.ToLower(strings.TrimSpace(value))
	if v == "" {
		e.Add(field, "Придумайте имя пользователя.")
		return ""
	}
	if len(v) < 3 {
		e.Add(field, "Имя пользователя — не короче 3 символов.")
		return v
	}
	if len(v) > 30 {
		e.Add(field, "Имя пользователя — не длиннее 30 символов.")
		return v
	}
	if !usernamePattern.MatchString(v) {
		e.Add(field, "Строчные латинские буквы, цифры, дефис и подчёркивание. Начинаться и заканчиваться — буквой или цифрой.")
		return v
	}
	if strings.Contains(v, "--") || strings.Contains(v, "__") {
		e.Add(field, "Два дефиса или два подчёркивания подряд использовать нельзя.")
		return v
	}
	if _, reserved := reservedUsernames[v]; reserved {
		e.Add(field, "Это имя зарезервировано. Выберите другое.")
	}
	return v
}

// Passwords that appear in every breach list. A length rule alone would let
// "password123" through, and the most common passwords are what credential
// stuffing actually tries.
var commonPasswords = map[string]struct{}{
	"password": {}, "password1": {}, "password123": {}, "passw0rd": {},
	"12345678": {}, "123456789": {}, "1234567890": {}, "qwertyuiop": {},
	"qwerty123": {}, "111111111": {}, "iloveyou": {}, "admin123": {},
	"welcome1": {}, "letmein1": {}, "monkey123": {}, "dragon123": {},
	"sunshine1": {}, "princess1": {}, "football1": {}, "baseball1": {},
	"trustno1": {}, "superman1": {}, "starwars1": {}, "whatever1": {},
	"averix123": {}, "developer1": {}, "changeme1": {}, "secret123": {},
}

// Password checks strength without imposing character-class theatre: length
// and not being obviously guessable is what actually helps.
func (e *Errors) Password(field, value string, minLength int) {
	if value == "" {
		e.Add(field, "Придумайте пароль.")
		return
	}
	n := utf8.RuneCountInString(value)
	if n < minLength {
		e.Addf(field, "Пароль — не короче %d символов.", minLength)
		return
	}
	if n > 200 {
		e.Add(field, "Такой длинный пароль мы принять не можем.")
		return
	}
	lower := strings.ToLower(value)
	if _, common := commonPasswords[lower]; common {
		e.Add(field, "Этот пароль слишком распространён. Придумайте тот, который труднее подобрать.")
		return
	}
	// A single repeated character passes any length rule.
	if distinctRunes(value) < 5 {
		e.Add(field, "В пароле слишком мало разных символов. Придумайте тот, который труднее подобрать.")
	}
}

func distinctRunes(s string) int {
	seen := map[rune]struct{}{}
	for _, r := range s {
		seen[r] = struct{}{}
	}
	return len(seen)
}

// ── Numbers and enums ───────────────────────────────────────────────────────

func (e *Errors) IntRange(field, label string, value, min, max int) {
	if value < min || value > max {
		e.Addf(field, "«%s»: значение от %d до %d.", label, min, max)
	}
}

// MoneyMinor validates an amount in minor units.
func (e *Errors) MoneyMinor(field, label string, value, min, max int64) {
	if value < min {
		e.Addf(field, "«%s»: не меньше %s.", label, formatMinor(min))
		return
	}
	if max > 0 && value > max {
		e.Addf(field, "«%s»: не больше %s.", label, formatMinor(max))
	}
}

func formatMinor(v int64) string {
	return fmt.Sprintf("%d.%02d", v/100, v%100)
}

// OneOf checks membership in a closed set.
func (e *Errors) OneOf(field, label, value string, allowed ...string) string {
	v := strings.TrimSpace(value)
	for _, a := range allowed {
		if v == a {
			return v
		}
	}
	e.Addf(field, "«%s»: допустимые значения — %s.", label, strings.Join(allowed, ", "))
	return v
}

// Currency validates an ISO-4217 code.
func (e *Errors) Currency(field, value string) string {
	v := strings.ToUpper(strings.TrimSpace(value))
	if v == "" {
		return "RUB"
	}
	if len(v) != 3 {
		e.Add(field, "Код валюты — три латинские буквы, например RUB.")
		return v
	}
	for i := 0; i < 3; i++ {
		if v[i] < 'A' || v[i] > 'Z' {
			e.Add(field, "Код валюты — три латинские буквы, например RUB.")
			return v
		}
	}
	return v
}

// ── Text hygiene ────────────────────────────────────────────────────────────

var (
	urlInText     = regexp.MustCompile(`(?i)\b(?:https?://|www\.)\S+`)
	emailInText   = regexp.MustCompile(`(?i)\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b`)
	phoneInText   = regexp.MustCompile(`(?:\+\d[\d\s().-]{7,}\d)`)
	messengerHint = regexp.MustCompile(`(?i)\b(?:t\.me/|telegram|whatsapp|skype|wechat|viber)\s*[:@]?\s*[\w.+-]{3,}`)
)

// ContactDetails reports contact information found in free text.
//
// Used on proposals and pre-hire messages. It flags for moderation rather than
// blocking: a legitimate proposal may well cite a GitHub URL, and silently
// refusing a developer's work with no explanation is worse than a review queue.
func ContactDetails(text string) []string {
	var found []string
	if urlInText.MatchString(text) {
		found = append(found, "url")
	}
	if emailInText.MatchString(text) {
		found = append(found, "email")
	}
	if phoneInText.MatchString(text) {
		found = append(found, "phone")
	}
	if messengerHint.MatchString(text) {
		found = append(found, "messenger")
	}
	return found
}

// LooksLikeSpam catches the proposals the product is designed to prevent:
// three words, no substance, sent to fifty projects.
func LooksLikeSpam(text string) bool {
	trimmed := strings.TrimSpace(text)
	if utf8.RuneCountInString(trimmed) < 40 {
		return true
	}
	words := strings.Fields(strings.ToLower(trimmed))
	if len(words) < 8 {
		return true
	}
	// A wall of one repeated word passes a length check.
	unique := map[string]struct{}{}
	for _, w := range words {
		unique[w] = struct{}{}
	}
	return float64(len(unique))/float64(len(words)) < 0.35
}

// Slugify produces a URL-safe slug matching the database's slugify().
func Slugify(input string) string {
	var b strings.Builder
	lastDash := true
	for _, r := range strings.ToLower(input) {
		switch {
		case r >= 'a' && r <= 'z', r >= '0' && r <= '9':
			b.WriteRune(r)
			lastDash = false
		case transliterate[r] != 0:
			b.WriteRune(transliterate[r])
			lastDash = false
		default:
			if !lastDash {
				b.WriteByte('-')
				lastDash = true
			}
		}
	}
	return strings.Trim(b.String(), "-")
}

// Enough coverage for the Latin-1 accents and the Cyrillic alphabet, so a
// Russian project title produces a readable slug rather than an empty one.
var transliterate = map[rune]rune{
	'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a', 'å': 'a',
	'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e',
	'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i',
	'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o',
	'ù': 'u', 'ú': 'u', 'û': 'u', 'ü': 'u',
	'ý': 'y', 'ÿ': 'y', 'ñ': 'n', 'ç': 'c', 'ß': 's',
	'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
	'ж': 'z', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
	'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
	'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'c', 'ш': 's', 'щ': 's', 'ы': 'y',
	'э': 'e', 'ю': 'u', 'я': 'a',
}
