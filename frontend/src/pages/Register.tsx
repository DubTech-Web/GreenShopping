import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApp } from "../store";
import { api, ApiError } from "../api";
import { EyeIcon, Leaf } from "../components";

export default function Register() {
  const { register, login } = useApp();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [code, setCode] = useState("");
  const [verification, setVerification] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
    if (password !== confirmPassword) { setError("Passwords do not match."); return; }
    setBusy(true); setError("");
    try {
      const devCode = await register(name, email, password);
      if (devCode) setCode(devCode);
      setVerification(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed");
    } finally { setBusy(false); }
  };

  const verify = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setError("");
    try {
      await api.verifyEmail(email, code);
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Verification failed");
    } finally { setBusy(false); }
  };

  if (verification) return (
    <div className="auth-wrap"><form className="card card-pad auth-card stack" onSubmit={verify}>
      <h1 style={{ margin: 0 }}>Verify your email</h1>
      <p className="muted">Enter the 6-digit code sent to {email}.</p>
      {error && <div className="alert alert-error" role="alert">{error}</div>}
      <input className="input" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required
        value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} aria-label="Verification code" />
      <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "Verifying…" : "Verify"}</button>
      <button type="button" className="btn btn-ghost" disabled={busy} onClick={async () => {
        try { const response = await api.resendCode(email); if (response.dev_code) setCode(response.dev_code); }
        catch (err) { setError(err instanceof ApiError ? err.message : "Could not resend code"); }
      }}>Resend code</button>
    </form></div>
  );

  return (
    <div className="auth-wrap">
      <form className="card card-pad auth-card stack" onSubmit={submit}>
        <div className="center-text stack" style={{ gap: 4 }}>
          <div className="row" style={{ justifyContent: "center", color: "var(--moss)" }}>
            <Leaf className="brand-leaf" />
          </div>
          <h1 style={{ margin: 0 }}>Create your account</h1>
          <p className="muted">Join GreenShopping and shop more sustainably.</p>
        </div>
        {error && <div className="alert alert-error" role="alert">{error}</div>}
        <div className="field">
          <label className="label" htmlFor="name">Name</label>
          <input id="name" className="input" required value={name}
            onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label className="label" htmlFor="email">Email</label>
          <input id="email" className="input" type="email" required autoComplete="email"
            value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label className="label" htmlFor="password">Password</label>
          <div className="password-input-wrap">
            <input id="password" className="input password-input" type={showPassword ? "text" : "password"} required minLength={8}
              autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <button type="button" className="password-toggle" aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword} onClick={() => setShowPassword((shown) => !shown)}>
              <EyeIcon hidden={showPassword} />
            </button>
          </div>
          <span className="muted" style={{ fontSize: "0.8rem" }}>At least 8 characters.</span>
        </div>
        <div className="field">
          <label className="label" htmlFor="confirm-password">Confirm password</label>
          <div className="password-input-wrap">
            <input id="confirm-password" className="input password-input" type={showPassword ? "text" : "password"} required minLength={8}
              autoComplete="new-password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
            <button type="button" className="password-toggle" aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword} onClick={() => setShowPassword((shown) => !shown)}>
              <EyeIcon hidden={showPassword} />
            </button>
          </div>
        </div>
        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
        <p className="muted center-text">Already have an account? <Link to="/login">Log in</Link></p>
      </form>
    </div>
  );
}
