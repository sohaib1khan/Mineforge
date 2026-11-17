import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import {
  ApiError,
  createUser,
  deleteUser,
  fetchUsers,
  resetUserPassword,
  updateUser,
} from "../../lib/api";
import type { UserRole } from "../../lib/types";
import { useAuth } from "../auth/AuthContext";

export function UsersPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const usersQuery = useQuery({ queryKey: ["users"], queryFn: fetchUsers });
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("player");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["users"] });
  };

  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: async () => {
      setUsername("");
      setPassword("");
      setRole("player");
      setMessage("User created.");
      setError(null);
      await invalidate();
    },
    onError: (err: unknown) => {
      setMessage(null);
      setError(err instanceof ApiError ? err.message : "Create failed");
    },
  });

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate({ username, password, role });
  }

  if (user?.role !== "admin") {
    return (
      <p className="text-danger" role="alert">
        Admin access required.
      </p>
    );
  }

  return (
    <section className="mx-auto w-full max-w-3xl space-y-8">
      <div className="space-y-1">
        <h1 className="font-pixel text-2xl">Users</h1>
        <p className="text-sm text-muted">
          Create accounts, reset passwords, and deactivate users.
        </p>
      </div>

      <form className="grid gap-3 sm:grid-cols-2" onSubmit={onCreate}>
        <Input
          label="Username"
          name="new_username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          minLength={3}
        />
        <Input
          label="Temporary password"
          name="new_password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={12}
        />
        <Select
          label="Role"
          name="role"
          value={role}
          onChange={(e) => setRole(e.target.value as UserRole)}
        >
          <option value="player">Player</option>
          <option value="admin">Admin</option>
        </Select>
        <div className="flex items-end">
          <Button type="submit" disabled={createMutation.isPending} className="w-full">
            {createMutation.isPending ? "Creating…" : "Add user"}
          </Button>
        </div>
      </form>

      {error ? <p className="text-sm text-danger">{error}</p> : null}
      {message ? <p className="text-sm text-primary">{message}</p> : null}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-border text-muted">
              <th className="py-2 pr-3 font-medium">User</th>
              <th className="py-2 pr-3 font-medium">Role</th>
              <th className="py-2 pr-3 font-medium">Status</th>
              <th className="py-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {(usersQuery.data?.users ?? []).map((row) => (
              <tr key={row.id} className="border-b border-border/70">
                <td className="py-3 pr-3 text-text">{row.username}</td>
                <td className="py-3 pr-3 capitalize text-muted">{row.role}</td>
                <td className="py-3 pr-3 text-muted">
                  {row.is_active ? "Active" : "Inactive"}
                  {row.must_change_password ? " · must change password" : ""}
                </td>
                <td className="py-3">
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      onClick={async () => {
                        const next = window.prompt(
                          `New password for ${row.username} (min 12 chars)`,
                        );
                        if (!next) return;
                        try {
                          await resetUserPassword(row.id, next);
                          setMessage(`Password reset for ${row.username}.`);
                          setError(null);
                          await invalidate();
                        } catch (err) {
                          setError(
                            err instanceof ApiError ? err.message : "Reset failed",
                          );
                        }
                      }}
                    >
                      Reset password
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={async () => {
                        try {
                          await updateUser(row.id, { is_active: !row.is_active });
                          setMessage(
                            `${row.username} ${row.is_active ? "deactivated" : "activated"}.`,
                          );
                          setError(null);
                          await invalidate();
                        } catch (err) {
                          setError(
                            err instanceof ApiError ? err.message : "Update failed",
                          );
                        }
                      }}
                    >
                      {row.is_active ? "Deactivate" : "Activate"}
                    </Button>
                    <Button
                      variant="danger"
                      onClick={async () => {
                        if (!window.confirm(`Delete ${row.username}?`)) return;
                        try {
                          await deleteUser(row.id);
                          setMessage(`${row.username} deleted.`);
                          setError(null);
                          await invalidate();
                        } catch (err) {
                          setError(
                            err instanceof ApiError ? err.message : "Delete failed",
                          );
                        }
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
