import { useState } from "react";
import { Send, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { PageHeader } from "@/components/ui/ModuleStatus";
import { Panel } from "@/components/ui/Panel";
import { askAssistant, type AssistantReply } from "@/lib/intelligenceApi";
import { useModules } from "@/lib/queries";
import { useUiStore } from "@/store/ui";

const SUGGESTIONS = [
  "How many detections in this period?",
  "Top activity cells",
  "Compare MODIS and VIIRS",
  "Any anomalies?",
  "How many cross-sensor matches?",
];

export function AssistantPage() {
  const dateRange = useUiStore((state) => state.dateRange);
  const { data: modules } = useModules();
  const module = modules?.find((item) => item.key === "assistant");

  const [question, setQuestion] = useState("");
  const [replies, setReplies] = useState<Array<{ question: string; reply: AssistantReply }>>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    try {
      const reply = await askAssistant(trimmed, dateRange.start, dateRange.end);
      setReplies((current) => [...current, { question: trimmed, reply }]);
      setQuestion("");
    } catch {
      setError("The assistant could not answer. Check the API.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Firewatch X / Intelligence"
        title="AI Assistant"
        status={module?.status}
        phase={module?.phase}
        description="Ask a question about the stored detections. Answers are computed from the same aggregates as the screens — no language model writes them, and every reply states its intent and scope."
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Panel title="Conversation" subtitle="Deterministic answers, newest last.">
          {replies.length === 0 ? (
            <p className="text-2xs font-light leading-relaxed text-muted">
              Ask one of the questions on the right, or type your own.
            </p>
          ) : (
            <ul className="space-y-4">
              {replies.map((entry, index) => (
                <li key={`${entry.question}-${index}`} className="space-y-2">
                  <div className="rounded-control border border-line/[0.08] bg-line/[0.03] px-3 py-2 text-2xs text-ink">
                    {entry.question}
                  </div>
                  <div className="rounded-control border border-accent/20 bg-accent/[0.04] px-3 py-2">
                    <p className="text-xs font-light leading-relaxed text-muted">
                      {entry.reply.answer}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-3xs text-faint">
                      <Badge tone="ok">{entry.reply.intent}</Badge>
                      <span className="font-mono">
                        {entry.reply.scope.start_date} → {entry.reply.scope.end_date}
                      </span>
                      {entry.reply.scope.place ? (
                        <span className="font-mono">{entry.reply.scope.place}</span>
                      ) : null}
                      <span>{entry.reply.method}</span>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}

          {error ? <p className="mt-3 text-2xs text-danger">{error}</p> : null}

          <form
            className="mt-4 flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              void ask(question);
            }}
          >
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="How many detections in Nigeria?"
              aria-label="Ask the assistant"
              className="w-full rounded-control border border-line/10 bg-canvas/60 px-3 py-2 text-xs text-ink"
            />
            <button
              type="submit"
              disabled={busy || !question.trim()}
              className="btn-primary inline-flex items-center gap-1.5 px-3 text-xs disabled:opacity-40"
            >
              <Send className="size-3.5" aria-hidden />
              {busy ? "…" : "Ask"}
            </button>
          </form>
        </Panel>

        <Panel title="What it can answer" subtitle="Fixed intents over real data.">
          <ul className="space-y-[6px]">
            {SUGGESTIONS.map((suggestion) => (
              <li key={suggestion}>
                <button
                  type="button"
                  onClick={() => void ask(suggestion)}
                  className="flex w-full items-center gap-2 rounded-control border border-line/[0.08] px-3 py-2 text-left text-2xs text-muted transition-colors duration-150 hover:border-line/25 hover:text-ink"
                >
                  <Sparkles className="size-3 text-faint" aria-hidden />
                  {suggestion}
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-3 border-t border-line/[0.07] pt-3 text-3xs font-light leading-relaxed text-faint">
            No model is called. Answers come from totals, ranked cells, sensor splits and the
            anomaly engine, and are limited to the period in the header.
          </p>
        </Panel>
      </div>
    </>
  );
}
