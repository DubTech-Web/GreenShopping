import { useState } from "react";
import { api, ApiError } from "../api";
import { ErrorNote, Spinner } from "../components";
import { useApp } from "../store";

export default function Profile() {
  const { customer } = useApp();
  const [name, setName] = useState(customer?.name ?? "");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  if (!customer) return <Spinner />;

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true); setError(""); setMessage("");
    try {
      await api.updateProfile(name.trim());
      setMessage("Profile updated.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update profile");
    } finally { setSaving(false); }
  };

  return (
    <div className="stack" style={{ maxWidth: 640, margin: "0 auto" }}>
      <h1>Profile</h1>
      <form className="card card-pad stack" onSubmit={save}>
        {error && <ErrorNote message={error} />}
        {message && <div className="alert alert-info" role="status">{message}</div>}
        <div className="field">
          <label className="label" htmlFor="profile-name">Name</label>
          <input id="profile-name" className="input" required maxLength={120} value={name}
            onChange={(event) => setName(event.target.value)} />
        </div>
        <div className="field"><span className="label">Email</span><span>{customer.email}</span></div>
        <div className="field"><span className="label">Account status</span><span className="badge badge-eco">Verified</span></div>
        <div className="field"><span className="label">Registered</span><span>{new Date(customer.created_at).toLocaleDateString()}</span></div>
        <button className="btn btn-primary" disabled={saving}>{saving ? "Saving…" : "Save profile"}</button>
      </form>
    </div>
  );
}
