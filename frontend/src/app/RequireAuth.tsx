import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";

export function RequireAuth() {
  const { user, needsSetup, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-muted">
        Loading…
      </div>
    );
  }

  if (needsSetup) {
    return <Navigate to="/setup" replace />;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}

export function RequireAdmin() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-muted">
        Loading…
      </div>
    );
  }

  if (!user || user.role !== "admin") {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}

export function PublicOnly() {
  const { user, needsSetup, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-muted">
        Loading…
      </div>
    );
  }

  if (needsSetup) {
    return <Navigate to="/setup" replace />;
  }

  if (user) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}

export function SetupOnly() {
  const { needsSetup, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-muted">
        Loading…
      </div>
    );
  }

  if (!needsSetup) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
