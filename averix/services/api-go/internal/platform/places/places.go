// Package places turns the codes a form collects into the words a person
// reads.
//
// A country is stored as its ISO-3166 alpha-2 code, because that is what the
// rest of the world agrees on. "Душанбе, TJ" is a database row shown to a
// person; "Душанбе, Таджикистан" is a place. The list covers the countries
// this marketplace actually serves and falls back to the code rather than
// inventing a name — an unknown code is a gap to fill, not a bug to hide.
package places

import "strings"

var countries = map[string]string{
	"RU": "Россия", "UZ": "Узбекистан", "KZ": "Казахстан", "TJ": "Таджикистан",
	"KG": "Киргизия", "TM": "Туркмения", "AZ": "Азербайджан", "AM": "Армения",
	"GE": "Грузия", "BY": "Беларусь", "UA": "Украина", "MD": "Молдавия",
	"TR": "Турция", "AE": "ОАЭ", "IL": "Израиль", "RS": "Сербия",
	"DE": "Германия", "PL": "Польша", "CZ": "Чехия", "LT": "Литва",
	"LV": "Латвия", "EE": "Эстония", "US": "США", "CA": "Канада",
	"GB": "Великобритания", "FR": "Франция", "ES": "Испания", "IT": "Италия",
	"NL": "Нидерланды", "PT": "Португалия", "CY": "Кипр", "TH": "Таиланд",
	"VN": "Вьетнам", "ID": "Индонезия", "IN": "Индия", "CN": "Китай",
	"MN": "Монголия", "AR": "Аргентина", "BR": "Бразилия", "MX": "Мексика",
}

// Country names a code, or returns the code when it is not one we know.
func Country(code string) string {
	code = strings.ToUpper(strings.TrimSpace(code))
	if name, ok := countries[code]; ok {
		return name
	}
	return code
}

// Format writes a city and a country the way an address is read: the smaller
// place first.
func Format(city, countryCode string) string {
	city = strings.TrimSpace(city)
	country := Country(countryCode)
	switch {
	case city != "" && country != "":
		return city + ", " + country
	case country != "":
		return country
	default:
		return city
	}
}
