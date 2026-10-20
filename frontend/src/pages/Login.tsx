import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useApp } from "../store";
import { api, ApiError } from "../api";
import { EyeIcon, Leaf } from "../components";

export default function Login() {
  const { login } = useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string })?.from ?? "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showResetPassword, setShowResetPassword] = useState(false);
  const [resetMode, setResetMode] = useState(false);
  const [resetCode, setResetCode] = useState("");
  const [resetPassword, setResetPassword] = useState("");
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

  const forgot = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const response = await api.forgotPassword(email);
      if (response.dev_code) setResetCode(response.dev_code);
      setResetMode(true);
    } catch (err) { setError(err instanceof ApiError ? err.message : "Could not start password reset"); }
    finally { setBusy(false); }
  };

  const reset = async () => {
    setBusy(true); setError("");
    try {
      await api.resetPassword(email, resetCode, resetPassword);
      setResetMode(false); setError("Password updated. You can now log in.");
    } catch (err) { setError(err instanceof ApiError ? err.message : "Could not reset password"); }
    finally { setBusy(false); }
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
          <div className="password-input-wrap">
            <input id="password" className="input password-input" type={showPassword ? "text" : "password"} required autoComplete="current-password"
              value={password} onChange={(e) => setPassword(e.target.value)} />
            <button type="button" className="password-toggle" aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword} onClick={() => setShowPassword((shown) => !shown)}>
              <EyeIcon hidden={showPassword} />
            </button>
          </div>
        </div>
        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? "Logging in…" : "Log in"}
        </button>
        <button type="button" className="btn btn-ghost btn-block" onClick={() => setResetMode((mode) => !mode)}>
          Forgot password?
        </button>
        {resetMode && <div className="panel stack">
          <strong>Reset password</strong>
          <button type="button" className="btn btn-accent btn-sm" onClick={forgot} disabled={busy}>Send reset code</button>
          <input className="input" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} placeholder="6-digit code" required value={resetCode} onChange={(e) => setResetCode(e.target.value.replace(/\D/g, ""))} />
          <div className="password-input-wrap">
            <input className="input password-input" type={showResetPassword ? "text" : "password"} minLength={8}
              placeholder="New password" required value={resetPassword} onChange={(e) => setResetPassword(e.target.value)} />
            <button type="button" className="password-toggle" aria-label={showResetPassword ? "Hide password" : "Show password"}
              aria-pressed={showResetPassword} onClick={() => setShowResetPassword((shown) => !shown)}>
              <EyeIcon hidden={showResetPassword} />
            </button>
          </div>
          <button type="button" className="btn btn-primary" disabled={busy} onClick={reset}>Update password</button>
        </div>}
        <p className="muted center-text">No account? <Link to="/register">Create one</Link></p>
      </form>
    </div>
  );
}
