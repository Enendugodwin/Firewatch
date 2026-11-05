import { KeyRound } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/ModuleStatus";
import { Panel } from "@/components/ui/Panel";
import { apiFetch } from "@/lib/api";

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await apiFetch("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      navigate("/admin");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setPending(false);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Firewatch X / Security"
        title="Operator sign-in"
        description="Role-based accounts (admin, analyst, viewer) with Argon2id passwords and server-side sessions. Readers do not need an account unless the deployment requires one."
      />
      <Panel
        title="Sign in"
        subtitle="The session cookie is HttpOnly; the browser never holds a password or token in JavaScript."
      >
        <form onSubmit={submit} className="max-w-md space-y-3">
          <label className="flex flex-col gap-1 text-2xs text-faint">
            Email
            <input
              type="email"
              value={email}
              autoComplete="username"
              onChange={(event) => setEmail(event.target.value)}
              className="rounded-lg border border-line/10 bg-line/[0.03] px-3 py-2 text-xs text-ink"
              required
            />
          </label>
          <label className="flex flex-col gap-1 text-2xs text-faint">
            Password
            <input
              type="password"
              value={password}
              autoComplete="current-password"
              onChange={(event) => setPassword(event.target.value)}
              className="rounded-lg border border-line/10 bg-line/[0.03] px-3 py-2 text-xs text-ink"
              required
            />
          </label>
          {error ? <p className="text-2xs text-danger">{error}</p> : null}
          <Button variant="primary" type="submit" disabled={pending}>
            <KeyRound className="size-3" aria-hidden />
            {pending ? "Signing in…" : "Sign in"}
          </Button>
          <p className="text-2xs leading-relaxed text-faint">
            No account yet? An administrator can create one with{" "}
            <code className="rounded bg-line/[0.06] px-1 py-[1px]">
              python -m scripts.create_admin --email you@example.com
            </code>
            .
          </p>
        </form>
      </Panel>
    </>
  );
}
