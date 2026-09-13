// Package money renders integer minor units as text a person reads.
//
// Money is stored and moved as an integer number of minor units with an
// explicit currency, and it is formatted in exactly one place so that a
// milestone, a proposal and a notification never disagree about what the same
// amount looks like.
package money

import (
	"fmt"
	"strings"
)

// unit says how a currency is written: the symbol, and whether it follows the
// number. Russian typography puts ₽ after the amount and $ before it, and
// getting that backwards reads as a machine translation.
type unit struct {
	symbol string
	suffix bool
}

var units = map[string]unit{
	"RUB": {"₽", true},
	"UZS": {"сум", true},
	"KZT": {"₸", true},
	"UAH": {"₴", true},
	"BYN": {"Br", true},
	"USD": {"$", false},
	"EUR": {"€", false},
	"GBP": {"£", false},
}

// Format writes an amount with a thin space between thousands and a comma
// before the kopecks, which is how numbers are written in Russian.
func Format(minor int64, currency string) string {
	code := strings.ToUpper(strings.TrimSpace(currency))
	u, known := units[code]
	if !known {
		// An empty code means "the number alone", for the left half of a
		// range whose currency is named once on the right.
		u = unit{code, true}
	}

	negative := minor < 0
	if negative {
		minor = -minor
	}
	whole := Thousands(minor / 100)
	text := whole
	if cents := minor % 100; cents != 0 {
		text = fmt.Sprintf("%s,%02d", whole, cents)
	}
	if negative {
		text = "−" + text
	}
	if u.symbol == "" {
		return text
	}
	if u.suffix {
		return text + " " + u.symbol
	}
	return u.symbol + text
}

// Round drops the minor units, for the places where "15 000 ₽" is easier to
// compare at a glance than "15 000,00 ₽".
func Round(minor int64, currency string) string {
	return Format(minor/100*100, currency)
}

// Range renders a budget or a price band.
func Range(min, max *int64, currency string) string {
	switch {
	case min != nil && max != nil && *min != *max:
		return Span(*min, *max, currency)
	case max != nil:
		return Round(*max, currency)
	case min != nil:
		return "от " + Round(*min, currency)
	}
	return ""
}

// Thousands groups digits with a non-breaking thin space, so an amount never
// wraps in the middle on a narrow screen.
func Thousands(v int64) string {
	digits := fmt.Sprintf("%d", v)
	if len(digits) <= 3 {
		return digits
	}
	var b strings.Builder
	lead := len(digits) % 3
	if lead > 0 {
		b.WriteString(digits[:lead])
	}
	for i := lead; i < len(digits); i += 3 {
		if b.Len() > 0 {
			b.WriteString(" ")
		}
		b.WriteString(digits[i : i+3])
	}
	return b.String()
}

// Bracket rounds an amount down to a band and returns that band, so a figure
// can be shown at the right order of magnitude without being exact.
//
// The step is proportional rather than a fixed table: a marketplace that
// prices in roubles, dollars and som has no single set of thresholds that is
// meaningful in all three, and a table tuned for one currency puts every
// amount in the last bucket for another.
func Bracket(minor int64) (int64, int64) {
	if minor <= 0 {
		return 0, 0
	}
	step := niceStep(minor / 2)
	lower := minor / step * step
	return lower, lower + step
}

// niceStep is the largest 1-2-5 round number not greater than v, which is how
// a person would pick a band by hand.
func niceStep(v int64) int64 {
	const floor = 50_00
	if v <= floor {
		return floor
	}
	best := int64(floor)
	for base := int64(100); base <= v; base *= 10 {
		for _, multiple := range []int64{1, 2, 5} {
			if candidate := base * multiple; candidate <= v && candidate > best {
				best = candidate
			}
		}
	}
	return best
}

// Band renders Bracket as text: "25 000 – 50 000 ₽", or "до 5 000 ₽" when the
// amount sits in the first band and a lower bound of zero would say nothing.
func Band(minor int64, currency string) string {
	lower, upper := Bracket(minor)
	if lower == 0 {
		return "до " + Round(upper, currency)
	}
	return Span(lower, upper, currency)
}

// Span writes a pair of amounts with the currency named once, the way a price
// range is written by hand: "1 000 – 1 500 ₽", not "1 000 ₽ – 1 500 ₽".
func Span(from, to int64, currency string) string {
	u, known := units[strings.ToUpper(strings.TrimSpace(currency))]
	if !known {
		return Round(from, currency) + " – " + Round(to, currency)
	}
	if u.suffix {
		return Round(from, "") + " – " + Round(to, currency)
	}
	return Round(from, currency) + " – " + strings.TrimPrefix(Round(to, currency), u.symbol)
}

// Visible applies the price-visibility ladder the two parties agreed on.
//
// "private" is rendered rather than omitted: the work happened, and hiding
// that it existed would misrepresent the person's history. Only the figure is
// withheld.
func Visible(minor int64, currency, visibility string) string {
	switch visibility {
	case "public":
		return Format(minor, currency)
	case "range":
		return Band(minor, currency)
	case "private":
		return "Закрытая сделка"
	default:
		return ""
	}
}
