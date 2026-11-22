/// One page of a paginated result.
class PageResult<T> {
  const PageResult({
    required this.items,
    required this.page,
    required this.hasMore,
    this.total,
  });

  const PageResult.empty()
    : items = const [],
      page = 1,
      hasMore = false,
      total = 0;

  final List<T> items;
  final int page;
  final bool hasMore;

  /// Total number of matches, when the source knows it.
  final int? total;
}
