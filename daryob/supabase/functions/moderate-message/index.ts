// AI check of a chat message for fraud and abuse.
//  warn  -> a safety notice is shown to the recipient, moderators see a flag;
//  block -> the message is hidden from the recipient as well.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { adminClient, isHook, json, cors } from "../_shared/hook.ts";
import { askJson, openAiKey } from "../_shared/openai.ts";

type Verdict = {
  risk: "none" | "warn" | "block";
  category: string;
  reason: string;
  warning_ru: string;
  warning_tg: string;
};

const SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["risk", "category", "reason", "warning_ru", "warning_tg"],
  properties: {
    risk: { type: "string", enum: ["none", "warn", "block"] },
    category: {
      type: "string",
      enum: ["none", "prepayment", "card_or_code", "phishing_link", "fake_delivery", "insult", "threat", "sexual", "spam", "prohibited", "other"],
    },
    reason: { type: "string" },
    warning_ru: { type: "string" },
    warning_tg: { type: "string" },
  },
};

const SYSTEM = `Ты проверяешь сообщения в чате покупателя и продавца на сайте объявлений DARYOB (Таджикистан).
Оцени ПОСЛЕДНЕЕ сообщение (предыдущие даны для контекста).

block — явная опасность: просит код из SMS/Telegram, данные карты (номер, срок, CVV), пароль; ссылка на поддельную оплату или «доставку»; угрозы; сексуальные домогательства; продажа запрещённого (оружие, наркотики).
warn — подозрительно: требует предоплату или перевод до встречи; предлагает «безопасную сделку» через стороннюю ссылку; оскорбления; спам; уводит в другой мессенджер вместе с просьбой о предоплате.
none — обычный разговор о товаре, торг, договорённость о встрече, обмен номерами телефонов.

warning_ru / warning_tg — короткое предупреждение для получателя (1–2 предложения), без обвинений. Для none — пустые строки.
reason — коротко для модератора, на русском.`;

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  const admin = adminClient();
  if (!(await isHook(req, admin))) return json({ error: "forbidden" }, 403);
  if (!openAiKey()) return json({ status: "skipped", reason: "no_ai_key" });

  const { message_id: messageId } = await req.json().catch(() => ({}));
  if (typeof messageId !== "string") return json({ error: "bad_request" }, 400);

  const { data: m } = await admin.from("messages").select("*").eq("id", messageId).maybeSingle();
  if (!m || m.hidden) return json({ status: "skipped" });
  const { data: staff } = await admin.from("staff").select("user_id").eq("user_id", m.sender_id).maybeSingle();
  if (staff) return json({ status: "skipped" });

  const { data: c } = await admin.from("conversations").select("*").eq("id", m.conversation_id).single();
  const { data: recent } = await admin.from("messages").select("sender_id, text, created_at")
    .eq("conversation_id", m.conversation_id).lt("created_at", m.created_at)
    .order("created_at", { ascending: false }).limit(6);
  const role = (id: string) => (id === c.seller_id ? "продавец" : "покупатель");
  const history = (recent ?? []).reverse().map((r) => `${role(r.sender_id)}: ${r.text}`).join("\n");

  let v: Verdict;
  try {
    v = await askJson<Verdict>(SYSTEM, [{
      type: "text",
      text: `Объявление: ${c.listing_title}\n\nПредыдущие сообщения:\n${history || "(нет)"}\n\nПОСЛЕДНЕЕ (${role(m.sender_id)}): ${m.text}`,
    }], "message_verdict", SCHEMA);
  } catch (e) {
    return json({ status: "error", error: String((e as Error).message ?? e) });
  }
  if (v.risk === "none") return json({ status: "ok" });

  const recipient = m.sender_id === c.buyer_id ? c.seller_id : c.buyer_id;
  await admin.from("message_flags").insert({
    message_id: m.id, conversation_id: m.conversation_id, sender_id: m.sender_id,
    risk: v.risk, category: v.category, reason: v.reason,
  });

  if (v.risk === "block") {
    await admin.from("messages").update({ hidden: true }).eq("id", m.id);
    // The recipient never sees it: remove it from the chat preview and counters.
    const { data: prev } = await admin.from("messages").select("text").eq("conversation_id", c.id)
      .eq("hidden", false).order("created_at", { ascending: false }).limit(1).maybeSingle();
    const unreadField = recipient === c.buyer_id ? "buyer_unread" : "seller_unread";
    await admin.from("conversations").update({
      last_message: prev?.text ?? null,
      [unreadField]: Math.max(0, (c[unreadField] ?? 1) - 1),
    }).eq("id", c.id);
    await admin.from("notifications").delete().eq("user_id", recipient).eq("data->>messageId", m.id);
    await admin.from("chat_notices").insert({
      conversation_id: c.id, for_user: m.sender_id, code: "message_blocked",
      text_ru: "Сообщение не доставлено: оно нарушает правила безопасности DARYOB.",
      text_tg: "Паём расонида нашуд: он қоидаҳои амнияти DARYOB-ро вайрон мекунад.",
    });
  }

  if (v.warning_ru) {
    await admin.from("chat_notices").insert({
      conversation_id: c.id, for_user: recipient, code: `warn_${v.category}`,
      text_ru: v.warning_ru, text_tg: v.warning_tg || v.warning_ru,
    });
  }
  return json({ status: v.risk });
});
