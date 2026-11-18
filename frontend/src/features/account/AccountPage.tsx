import { useState, type FormEvent } from "react";

import { Icon, Icons } from "../../components/icons";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { useToast } from "../../components/ui/Toast";
import { ApiError, changePassword } from "../../lib/api";
import { useAuth } from "../auth/AuthContext";

export function AccountPage() {
  const { user, logout } = useAuth();
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
        <h1 className="font-pixel text-2xl inline-flex items-center gap-2">
          <Icon icon={Icons.Account} size={22} className="text-primary" />
          Account
        </h1>
        <p className="text-sm text-muted">
          Signed in as <span className="text-text">{user.username}</span> ({user.role})
        </p>
      </div>

      <div className="mf-card space-y-3 p-4">
        <p className="text-sm text-muted">
          Theme is available from the sidebar on desktop, or <strong>More</strong> on
          mobile — one place only.
        </p>
        <Button
          variant="secondary"
          className="w-full justify-start gap-2"
          onClick={() => void logout()}
        >
          <Icon icon={Icons.Logout} size={16} />
          Sign out
        </Button>
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
