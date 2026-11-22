import '../../../core/storage/local_database.dart';
import '../domain/listing_draft.dart';

/// Drafts always live on the device, in every environment.
class LocalDraftRepository implements DraftRepository {
  LocalDraftRepository(LocalDatabase database)
    : _drafts = database.collection(Collections.drafts);

  final JsonCollection _drafts;

  @override
  List<ListingDraft> all() =>
      _drafts.values().map(ListingDraft.fromJson).toList()
        ..sort((a, b) => b.updatedAt.compareTo(a.updatedAt));

  @override
  ListingDraft? get(String id) {
    final json = _drafts.get(id);
    return json == null ? null : ListingDraft.fromJson(json);
  }

  @override
  Future<void> save(ListingDraft draft) =>
      _drafts.put(draft.id, draft.toJson());

  @override
  Future<void> delete(String id) => _drafts.delete(id);
}
