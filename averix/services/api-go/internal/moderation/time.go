package moderation

import "time"

// timeOrNil scans a nullable timestamp without a pointer-to-pointer dance in
// the row scanner.
type timeOrNil struct{ time.Time }

func (t *timeOrNil) Scan(v any) error {
	switch x := v.(type) {
	case nil:
		return nil
	case time.Time:
		t.Time = x
	}
	return nil
}
