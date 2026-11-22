import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/providers/repository_providers.dart';
import '../../listings/domain/listing_query.dart';
import '../../settings/application/settings_controller.dart';

class SearchState {
  const SearchState({
    required this.query,
    required this.submitted,
    required this.history,
  });

  final ListingQuery query;

  /// False while the user is still typing / looking at history.
  final bool submitted;
  final List<String> history;

  SearchState copyWith({
    ListingQuery? query,
    bool? submitted,
    List<String>? history,
  }) {
    return SearchState(
      query: query ?? this.query,
      submitted: submitted ?? this.submitted,
      history: history ?? this.history,
    );
  }
}

/// Kept alive for the whole session so returning to search restores the
/// last query, filters and results.
final searchControllerProvider =
    NotifierProvider<SearchController, SearchState>(SearchController.new);

class SearchController extends Notifier<SearchState> {
  @override
  SearchState build() {
    final region = ref.read(settingsControllerProvider).regionId;
    return SearchState(
      query: ListingQuery(regionId: region),
      submitted: false,
      history: ref.read(searchHistoryRepositoryProvider).load(),
    );
  }

  /// Runs a search for [text] with the current filters.
  Future<void> submit(String text) async {
    final clean = text.trim();
    state = state.copyWith(
      query: state.query.copyWith(text: clean),
      submitted: clean.isNotEmpty || state.query.hasFilters,
    );
    if (clean.length >= 2) {
      final history = await ref
          .read(searchHistoryRepositoryProvider)
          .add(clean);
      state = state.copyWith(history: history);
    }
  }

  void applyFilters(ListingQuery query) {
    state = state.copyWith(query: query, submitted: true);
  }

  void setCategory(String? categoryId) {
    state = state.copyWith(
      query: categoryId == null
          ? state.query.copyWith(clearCategory: true)
          : state.query.copyWith(categoryId: categoryId),
      submitted: true,
    );
  }

  void showHistory() {
    state = state.copyWith(submitted: false);
  }

  Future<void> removeHistory(String phrase) async {
    final history = await ref
        .read(searchHistoryRepositoryProvider)
        .remove(phrase);
    state = state.copyWith(history: history);
  }

  Future<void> clearHistory() async {
    await ref.read(searchHistoryRepositoryProvider).clear();
    state = state.copyWith(history: const []);
  }
}
