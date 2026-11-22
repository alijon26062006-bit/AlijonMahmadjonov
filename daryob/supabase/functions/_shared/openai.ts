// Minimal OpenAI Chat Completions call with a strict JSON answer.
export type JsonSchema = Record<string, unknown>;

export function openAiKey(): string | null {
  return Deno.env.get("OPENAI_API_KEY") ?? null;
}

export function openAiModel(): string {
  return Deno.env.get("OPENAI_MODERATION_MODEL") ?? "gpt-5-mini";
}

export async function askJson<T>(
  system: string,
  content: unknown[],
  schemaName: string,
  schema: JsonSchema,
): Promise<T> {
  const key = openAiKey();
  if (!key) throw new Error("no_key");
  const body: Record<string, unknown> = {
    model: openAiModel(),
    messages: [
      { role: "system", content: system },
      { role: "user", content },
    ],
    response_format: {
      type: "json_schema",
      json_schema: { name: schemaName, strict: true, schema },
    },
    max_completion_tokens: 6000,
  };
  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { "Authorization": `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(`openai_${res.status}: ${data?.error?.message ?? ""}`.slice(0, 300));
  const text = data?.choices?.[0]?.message?.content;
  if (typeof text !== "string") throw new Error("openai_empty");
  return JSON.parse(text) as T;
}
