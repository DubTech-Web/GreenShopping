import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApp } from "../store";
import { ApiError } from "../api";
import { Leaf } from "../components";

export default function Register() {
  const { register } = useApp();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
    setBusy(true); setError("");
    try {
      await register(name, email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed");
    } finally { setBusy(false); }
  };

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
          <input id="password" className="input" type="password" required minLength={8}
            autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <span className="muted" style={{ fontSize: "0.8rem" }}>At least 8 characters.</span>
        </div>
        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
        <p className="muted center-text">Already have an account? <Link to="/login">Log in</Link></p>
      </form>
    </div>
  );
}
