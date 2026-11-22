import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../../app/localization/l10n.dart';
import '../../app/theme/tokens.dart';
import '../../core/backend/backend.dart';
import '../../shared/models/localized_text.dart';
import '../../shared/providers/core_providers.dart';

/// A city, town, village or district from the places directory
/// (GeoNames, CC BY 4.0), stored on the server.
@immutable
class Place {
  const Place({
    required this.id,
    required this.kind,
    required this.name,
    required this.regionId,
    required this.lat,
    required this.lng,
    this.cityId,
    this.population = 0,
  });

  final int id;

  /// city | town | village | quarter | district
  final String kind;
  final LocalizedText name;

  /// Top-level region id of the region directory (sughd, khatlon, ...).
  final String regionId;

  /// Directory city when the place is in or next to one.
  final String? cityId;
  final double lat;
  final double lng;
  final int population;

  /// The region-directory id a listing in this place belongs to.
  String get directoryId => cityId ?? regionId;

  factory Place.fromRow(Map<String, dynamic> row) => Place(
    id: (row['id'] as num).toInt(),
    kind: row['kind'] as String,
    name: LocalizedText(ru: row['name_ru'] as String, tg: row['name_tg'] as String),
    regionId: row['region_id'] as String,
    cityId: row['city_id'] as String?,
    lat: (row['lat'] as num).toDouble(),
    lng: (row['lng'] as num).toDouble(),
    population: (row['population'] as num?)?.toInt() ?? 0,
  );
}

class PlaceRepository {
  PlaceRepository(this._client);
  final SupabaseClient _client;

  Future<List<Place>> search(String query) {
    final q = query.trim();
    if (q.length < 2) return Future.value(const []);
    return backendCall(() async {
      final rows = await _client.rpc<dynamic>(
        'search_places',
        params: {'p_query': q, 'p_limit': 25},
      );
      return [
        for (final r in rows as List) Place.fromRow(Map<String, dynamic>.from(r as Map)),
      ];
    });
  }
}

/// Null when no server is connected (development builds).
final placeRepositoryProvider = Provider<PlaceRepository?>((ref) {
  final client = ref.watch(backendClientProvider);
  return client == null ? null : PlaceRepository(client);
});

String placeKindLabel(AppLocalizations l10n, String kind) => switch (kind) {
  'city' => l10n.placeCity,
  'town' => l10n.placeTown,
  'district' => l10n.placeDistrict,
  'quarter' => l10n.placeQuarter,
  _ => l10n.placeVillage,
};

/// Search field with results: "type the name of your village".
class PlaceSearchField extends ConsumerStatefulWidget {
  const PlaceSearchField({super.key, required this.onPicked});
  final ValueChanged<Place> onPicked;

  @override
  ConsumerState<PlaceSearchField> createState() => _PlaceSearchFieldState();
}

class _PlaceSearchFieldState extends ConsumerState<PlaceSearchField> {
  final _controller = TextEditingController();
  Timer? _debounce;
  List<Place> _results = const [];
  bool _loading = false;
  bool _failed = false;
  int _request = 0;

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () => _search(value));
  }

  Future<void> _search(String value) async {
    final repo = ref.read(placeRepositoryProvider);
    if (repo == null) return;
    final id = ++_request;
    setState(() {
      _loading = value.trim().length >= 2;
      _failed = false;
    });
    try {
      final results = await repo.search(value);
      if (!mounted || id != _request) return;
      setState(() {
        _results = results;
        _loading = false;
      });
    } catch (_) {
      if (!mounted || id != _request) return;
      setState(() {
        _loading = false;
        _failed = true;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final regions = ref.watch(regionDirectoryProvider);
    final query = _controller.text.trim();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          controller: _controller,
          onChanged: _onChanged,
          textInputAction: TextInputAction.search,
          decoration: InputDecoration(
            hintText: l10n.placeSearchHint,
            prefixIcon: const Icon(Icons.travel_explore_rounded),
            suffixIcon: _loading
                ? const Padding(
                    padding: EdgeInsets.all(14),
                    child: SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                : null,
          ),
        ),
        if (_failed)
          Padding(
            padding: const EdgeInsets.only(top: DaryobSpacing.xs),
            child: Text(l10n.placeSearchFailed, style: context.text.bodySmall),
          )
        else if (query.length >= 2 && !_loading && _results.isEmpty)
          Padding(
            padding: const EdgeInsets.only(top: DaryobSpacing.xs),
            child: Text(l10n.placeNotFound, style: context.text.bodySmall),
          ),
        if (_results.isNotEmpty)
          Container(
            margin: const EdgeInsets.only(top: DaryobSpacing.xs),
            constraints: const BoxConstraints(maxHeight: 300),
            decoration: BoxDecoration(
              color: context.colors.surface,
              borderRadius: DaryobRadius.inputAll,
              border: Border.all(color: context.palette.border),
            ),
            child: ListView.builder(
              shrinkWrap: true,
              itemCount: _results.length,
              itemBuilder: (context, i) {
                final p = _results[i];
                final region = regions.byId(p.regionId);
                return ListTile(
                  dense: true,
                  leading: Icon(
                    p.kind == 'village' ? Icons.cottage_outlined : Icons.location_city_outlined,
                    size: 20,
                  ),
                  title: Text(p.name.of(context)),
                  subtitle: Text(
                    [placeKindLabel(l10n, p.kind), if (region != null) region.name.of(context)].join(' · '),
                  ),
                  onTap: () {
                    FocusScope.of(context).unfocus();
                    setState(() {
                      _results = const [];
                      _controller.clear();
                    });
                    widget.onPicked(p);
                  },
                );
              },
            ),
          ),
      ],
    );
  }
}
