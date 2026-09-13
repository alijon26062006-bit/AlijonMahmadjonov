package validate

import "testing"

// Площадка русская, и название работы обычно тоже. Раньше «Обмен с 1С для
// оптовой базы» превращался в "1" — один символ, от цифры, потому что всё
// остальное выбрасывалось.
func TestSlugifyTransliteratesRussian(t *testing.T) {
	cases := map[string]string{
		"Обмен с 1С для оптовой базы":           "obmen-s-1s-dla-optovoi-bazy",
		"Логотип и вывеска для кофейни «Зерно»": "logotip-i-vyveska-dla-kofeini-zerno",
		"Warehouse stock API": "warehouse-stock-api",
	}
	for input, want := range cases {
		if got := Slugify(input); got != want {
			t.Errorf("Slugify(%q) = %q, want %q", input, got, want)
		}
	}
}
