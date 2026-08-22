// Route guards (Spec §25 — client-side gating; the API enforces auth server-side too).
import { type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useApp } from "./store";
import { Spinner } from "./components";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { customer, loading } = useApp();
  const location = useLocation();
  if (loading) return <Spinner />;
  if (!customer) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return <>{children}</>;
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { customer, loading } = useApp();
  if (loading) return <Spinner />;
  if (!customer) return <Navigate to="/login" replace />;
  if (!customer.is_admin) return <Navigate to="/" replace />;
  return <>{children}</>;
}
