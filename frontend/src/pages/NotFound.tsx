import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="panel center-text stack" style={{ padding: 60 }}>
      <h1 style={{ margin: 0 }}>404</h1>
      <p className="muted">That page could not be found.</p>
      <div><Link to="/" className="btn btn-primary">Go home</Link></div>
    </div>
  );
}
