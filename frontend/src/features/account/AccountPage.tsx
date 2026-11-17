import { useState, type FormEvent } from "react";

import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { useToast } from "../../components/ui/Toast";
import { ApiError, changePassword } from "../../lib/api";
import { useAuth } from "../auth/AuthContext";
import { useTheme } from "../theme/ThemeContext";

export function AccountPage() {
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();
  const toast = useToast();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      toast.push("Password updated.", "success");
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Could not update password";
      setError(message);
      toast.push(message, "error");
    } finally {
      setPending(false);
    }
  }

  if (!user) {
    return null;
  }

  return (
    <section className="mx-auto w-full max-w-lg space-y-8">
      <div className="space-y-1">
        <h1 className="font-pixel text-2xl">Account</h1>
        <p className="text-sm text-muted">
          Signed in as <span className="text-text">{user.username}</span> ({user.role})
        </p>
      </div>

      <div className="space-y-3">
        <h2 className="text-lg text-text">Theme</h2>
        <div className="flex gap-2" role="group" aria-label="Color theme">
          <Button
            variant={theme === "dark" ? "primary" : "secondary"}
            onClick={() => setTheme("dark")}
            aria-pressed={theme === "dark"}
          >
            Dark
          </Button>
          <Button
            variant={theme === "light" ? "primary" : "secondary"}
            onClick={() => setTheme("light")}
            aria-pressed={theme === "light"}
          >
            Light
          </Button>
        </div>
      </div>

      <form className="space-y-4" onSubmit={onSubmit}>
        <h2 className="text-lg text-text">Change password</h2>
        <Input
          label="Current password"
          name="current_password"
          type="password"
          autoComplete="current-password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          required
        />
        <Input
          label="New password"
          name="new_password"
          type="password"
          autoComplete="new-password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
          minLength={12}
        />
        {error ? (
          <p className="text-sm text-danger" role="alert">
            {error}
          </p>
        ) : null}
        <Button type="submit" disabled={pending}>
          {pending ? "Saving…" : "Update password"}
        </Button>
      </form>
    </section>
  );
}
