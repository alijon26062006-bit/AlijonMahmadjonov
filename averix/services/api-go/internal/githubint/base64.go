package githubint

import "encoding/base64"

// base64Decode is standard base64 with padding, which is what the GitHub
// contents API returns. Wrapped so the call site reads clearly.
func base64Decode(s string) ([]byte, error) {
	return base64.StdEncoding.DecodeString(s)
}
