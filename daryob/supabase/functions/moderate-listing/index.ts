// AI moderation of a listing: photos, category, title, description, price.
//
// Called by the database when a listing enters moderation. Clear cases are
// decided automatically; anything uncertain stays in the moderators' queue.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { adminClient, isHook, json, setAiStatus, cors } from "../_shared/hook.ts";
import { askJson, openAiKey, openAiModel } from "../_shared/openai.ts";

type Verdict = {
  decision: "approve" | "reject" | "review";
  confidence: number;
  photos_match: boolean;
  category_ok: boolean;
  suggested_category: string;
  problems: { code: string; ru: string; tg: string }[];
};

const SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["decision", "confidence", "photos_match", "category_ok", "suggested_category", "problems"],
  properties: {
    decision: { type: "string", enum: ["approve", "reject", "review"] },
    confidence: { type: "number" },
    photos_match: { type: "boolean" },
    category_ok: { type: "boolean" },
    suggested_category: { type: "string" },
    problems: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["code", "ru", "tg"],
        properties: { code: { type: "string" }, ru: { type: "string" }, tg: { type: "string" } },
      },
    },
  },
};

const SYSTEM = `Ты — модератор DARYOB, сайта частных объявлений в Таджикистане (цены в сомони, TJS).
Проверь объявление и реши: approve (публиковать), reject (отклонить) или review (нужен человек).

Отклоняй (reject), если явно:
- фото не соответствуют названию/категории (например, в «Смартфоны» фото машины), или фото нет смысла (скриншот, мем, чёрный экран);
- категория явно неверная (укажи правильную в suggested_category как id вида "vehicles.cars");
- запрещённые товары: оружие и боеприпасы, наркотики и их атрибутика, рецептурные лекарства, поддельные документы и деньги, краденое, персональные данные, услуги интим-характера, азартные игры, дикие и охраняемые животные, человеческие органы;
- откровенный контент, насилие, оскорбления, экстремизм;
- мошенничество: требование предоплаты на карту до встречи, «выигрыш», заведомо нереальная цена (iPhone за 100 сомони), ссылки на сторонние сайты оплаты;
- в тексте или на фото реклама других сайтов, ссылки, QR-коды;
- бессмыслица, тест, пустое описание, текст не про товар.

На review отправляй, если сомневаешься: фото плохого качества, цена подозрительная но возможная, спорный товар.
Обычные честные объявления — approve, даже если описание короткое. Номер телефона в описании не нарушение.

problems — список конкретных причин для продавца, коротко и вежливо, на русском (ru) и таджикском (tg).
Для approve problems пустой. confidence — от 0 до 1.`;

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  const admin = adminClient();
  if (!(await isHook(req, admin))) return json({ error: "forbidden" }, 403);

  const { listing_id: listingId, force } = await req.json().catch(() => ({}));
  if (typeof listingId !== "string") return json({ error: "bad_request" }, 400);

  const { data: l } = await admin.from("listings").select("*").eq("id", listingId).maybeSingle();
  if (!l) return json({ status: "not_found" });
  if (l.status !== "pending" && !force) return json({ status: "skipped" });

  if (!openAiKey()) {
    await setAiStatus(admin, false, "OPENAI_API_KEY is not set");
    await admin.from("listings").update({
      moderation: { decision: "review", note: "no_ai_key", checked_at: new Date().toISOString() },
    }).eq("id", listingId);
    return json({ status: "review", reason: "no_ai_key" });
  }

  const photos: string[] = (l.photos ?? []).slice(0, 6);
  const content: unknown[] = [{
    type: "text",
    text: JSON.stringify({
      category_id: l.category_id,
      title: l.title,
      description: l.description,
      price_tjs: l.price,
      negotiable: l.is_negotiable,
      attributes: l.attributes,
      region: l.region_id,
      place: l.place_name,
      photos_count: (l.photos ?? []).length,
    }),
  }];
  for (const url of photos) content.push({ type: "image_url", image_url: { url, detail: "low" } });
  if (photos.length === 0) content.push({ type: "text", text: "Фото нет." });

  let verdict: Verdict;
  try {
    verdict = await askJson<Verdict>(SYSTEM, content, "listing_verdict", SCHEMA);
    await setAiStatus(admin, true);
  } catch (e) {
    const message = String((e as Error).message ?? e);
    await setAiStatus(admin, true, message);
    await admin.from("listings").update({
      moderation: { decision: "review", note: "ai_error", error: message, checked_at: new Date().toISOString() },
    }).eq("id", listingId);
    return json({ status: "review", reason: "ai_error" });
  }

  const moderation = { ...verdict, model: openAiModel(), checked_at: new Date().toISOString() };
  const problems = verdict.problems ?? [];
  const now = new Date().toISOString();

  if (verdict.decision === "approve" && verdict.confidence >= 0.75 && problems.length === 0) {
    if (l.status === "pending") {
      await admin.from("listings").update({
        status: "active", published_at: now, moderation, moderated_at: now,
        rejection_reason: null, rejection_reason_tg: null,
      }).eq("id", listingId);
      await admin.from("notifications").insert({
        user_id: l.owner_id, kind: "listingApproved", title: "Объявление опубликовано", body: l.title,
        data: { title: l.title, listingId },
      });
    } else {
      await admin.from("listings").update({ moderation }).eq("id", listingId);
    }
    return json({ status: "approved" });
  }

  if (verdict.decision === "reject" && verdict.confidence >= 0.8 && problems.length > 0) {
    const ru = problems.map((p) => p.ru).join("\n");
    const tg = problems.map((p) => p.tg).join("\n");
    await admin.from("listings").update({
      status: "rejected", moderation, moderated_at: now, rejection_reason: ru, rejection_reason_tg: tg,
    }).eq("id", listingId);
    await admin.from("notifications").insert({
      user_id: l.owner_id, kind: "listingRejected", title: "Объявление отклонено", body: ru,
      data: { title: l.title, listingId, reason: ru, reason_tg: tg },
    });
    return json({ status: "rejected" });
  }

  await admin.from("listings").update({ moderation: { ...moderation, decision: "review" } }).eq("id", listingId);
  return json({ status: "review" });
});
