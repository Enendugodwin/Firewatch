import { ModuleScaffold } from "@/components/ui/ModuleScaffold";

export function AssistantPage() {
  return (
    <ModuleScaffold
      moduleKey="assistant"
      requirements={[
        "Approved analytical tools backed by real stored data.",
        "An LLM provider configured server-side (the platform works without one).",
        "Tool-call logging, so every answer can be traced to source records.",
      ]}
    />
  );
}
