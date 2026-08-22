import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useApp } from "../store";
import { ApiError } from "../api";
import { Leaf } from "../components";

export default function Login() {
  const { login } = useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string })?.from ?? "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="auth-wrap">
      <form className="card card-pad auth-card stack" onSubmit={submit}>
        <div className="center-text stack" style={{ gap: 4 }}>
          <div className="row" style={{ justifyContent: "center", color: "var(--moss)" }}>
            <Leaf className="brand-leaf" />
          </div>
          <h1 style={{ margin: 0 }}>Welcome back</h1>
          <p className="muted">Log in to your GreenShopping account.</p>
        </div>
        {error && <div className="alert alert-error" role="alert">{error}</div>}
        <div className="field">
          <label className="label" htmlFor="email">Email</label>
          <input id="email" className="input" type="email" required autoComplete="email"
            value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label className="label" htmlFor="password">Password</label>
          <input id="password" className="input" type="password" required autoComplete="current-password"
            value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? "Logging in…" : "Log in"}
        </button>
        <p className="muted center-text">No account? <Link to="/register">Create one</Link></p>
      </form>
    </div>
  );
}
