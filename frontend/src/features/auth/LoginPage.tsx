import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { APP_DISPLAY_NAME, AUTHOR_NAME, AUTHOR_URL } from "../../app/constants";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { ApiError } from "../../lib/api";
import { useAuth } from "./AuthContext";

export function LoginPage() {
  const { login, user, needsSetup, isLoading } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (!isLoading && needsSetup) {
    return <Navigate to="/setup" replace />;
  }
  if (!isLoading && user) {
    return <Navigate to="/" replace />;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      await login(username, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="mx-auto w-full max-w-md space-y-6">
      <div className="space-y-2">
        <h1 className="font-pixel text-2xl text-text">Sign in</h1>
        <p className="text-sm text-muted">
          Sign in to manage your {APP_DISPLAY_NAME} Bedrock server.
        </p>
      </div>
      <form className="space-y-4" onSubmit={onSubmit}>
        <Input
          label="Username"
          name="username"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />
        <Input
          label="Password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error ? <p className="text-sm text-danger">{error}</p> : null}
        <Button type="submit" className="w-full" disabled={pending}>
          {pending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
      <p className="text-center text-xs text-muted">
        Built by{" "}
        <a
          href={AUTHOR_URL}
          className="underline decoration-border underline-offset-2 hover:text-text"
          target="_blank"
          rel="noreferrer"
        >
          {AUTHOR_NAME}
        </a>
      </p>
    </section>
  );
}
