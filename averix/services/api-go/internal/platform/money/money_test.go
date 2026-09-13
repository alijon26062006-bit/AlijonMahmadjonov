package money

import "testing"

// The separator is a non-breaking space so an amount never wraps mid-number.
const nb = " "

func TestFormatPutsTheSymbolWhereTheLanguageExpectsIt(t *testing.T) {
	cases := []struct {
		minor    int64
		currency string
		want     string
	}{
		{1_500_00, "RUB", "1" + nb + "500 ₽"},
		{1_500_00, "USD", "$1" + nb + "500"},
		{1_500_50, "RUB", "1" + nb + "500,50 ₽"},
		{99, "RUB", "0,99 ₽"},
		{-2_000_00, "RUB", "−2" + nb + "000 ₽"},
		{12_00, "UZS", "12 сум"},
		{12_00, "XYZ", "12 XYZ"},
		{12_00, "", "12"},
	}
	for _, c := range cases {
		if got := Format(c.minor, c.currency); got != c.want {
			t.Errorf("Format(%d, %q) = %q, want %q", c.minor, c.currency, got, c.want)
		}
	}
}

// A band must hide the exact figure while keeping its scale readable, in any
// currency — that is the whole reason the step is proportional.
func TestBandScalesWithTheAmount(t *testing.T) {
	cases := []struct {
		minor    int64
		currency string
		want     string
	}{
		{120_000, "USD", "$1" + nb + "000 – 1" + nb + "500"},
		{15_000_00, "RUB", "15" + nb + "000 – 20" + nb + "000 ₽"},
		{250_00, "RUB", "200 – 300 ₽"},
		{1_000_000_00, "RUB", "1" + nb + "000" + nb + "000 – 1" + nb + "500" + nb + "000 ₽"},
		{30_00, "RUB", "до 50 ₽"},
	}
	for _, c := range cases {
		if got := Band(c.minor, c.currency); got != c.want {
			t.Errorf("Band(%d, %q) = %q, want %q", c.minor, c.currency, got, c.want)
		}
	}
}

// The band must always contain the amount it hides: a range that excludes the
// real figure is worse than showing nothing.
func TestBandContainsTheAmount(t *testing.T) {
	for _, minor := range []int64{1, 99, 4_999, 50_00, 1_234_56, 987_654_321} {
		lower, upper := Bracket(minor)
		if minor < lower || minor > upper {
			t.Errorf("Bracket(%d) = (%d, %d), which does not contain it", minor, lower, upper)
		}
	}
}

func TestVisibleWithholdsTheFigureButNotTheWork(t *testing.T) {
	if got := Visible(50_000_00, "RUB", "hidden"); got != "" {
		t.Errorf("hidden = %q, want nothing", got)
	}
	if got := Visible(50_000_00, "RUB", "private"); got != "Закрытая сделка" {
		t.Errorf("private = %q; the work must still be visible", got)
	}
	if got := Visible(50_000_00, "RUB", "public"); got != "50"+nb+"000 ₽" {
		t.Errorf("public = %q", got)
	}
}
