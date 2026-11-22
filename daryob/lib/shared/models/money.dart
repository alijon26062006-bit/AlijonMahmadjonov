enum Currency {
  tjs('TJS'),
  usd('USD');

  const Currency(this.code);
  final String code;

  static Currency fromCode(String? code) => Currency.values.firstWhere(
    (c) => c.code == code,
    orElse: () => Currency.tjs,
  );
}
