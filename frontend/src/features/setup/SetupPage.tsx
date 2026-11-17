import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { APP_DISPLAY_NAME } from "../../app/constants";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { ApiError, completeSetup } from "../../lib/api";

export function SetupPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    setPending(true);
    try {
      await completeSetup({ username, password });
      await queryClient.invalidateQueries({ queryKey: ["setup-status"] });
      navigate("/login", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Setup failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="mx-auto w-full max-w-md space-y-6">
      <div className="space-y-2">
        <h1 className="font-pixel text-2xl text-text">First-time setup</h1>
        <p className="text-sm text-muted leading-relaxed">
          Welcome to {APP_DISPLAY_NAME}. No admin account exists yet — create yours to
          finish installing this server.
        </p>
      </div>
      <form className="space-y-4" onSubmit={onSubmit}>
        <Input
          label="Admin username"
          name="username"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          minLength={3}
        />
        <Input
          label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={12}
        />
        <Input
          label="Confirm password"
          name="confirm_password"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          minLength={12}
        />
        {error ? <p className="text-sm text-danger">{error}</p> : null}
        <Button type="submit" className="w-full" disabled={pending}>
          {pending ? "Creating…" : "Create admin"}
        </Button>
      </form>
    </section>
  );
}
