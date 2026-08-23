import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import type { ProductDetail as Detail, Recommendation } from "../types";
import { EcoBadge, EcoScore, ErrorNote, money, Spinner, StockBadge } from "../components";
import { ProductImage } from "../productImage";
import { useApp } from "../store";

export default function ProductDetail() {
  const { id } = useParams();
  const { customer, refreshCart } = useApp();
  const [p, setP] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [qty, setQty] = useState(1);
  const [msg, setMsg] = useState("");

  // ONE request returns product + recommendations + eco alternative (Spec §17 optimization).
  useEffect(() => {
    let active = true;
    setLoading(true);
    api.product(Number(id))
      .then((d) => { if (active) { setP(d); setError(""); } })
      .catch((e) => { if (active) setError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);

  const add = async () => {
    if (!customer) { setMsg("Please log in to add items to your cart."); return; }
    try {
      await api.addToCart(p!.id, qty);
      await refreshCart();
      setMsg("Added to cart ✓");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Could not add to cart");
    }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorNote message={error} />;
  if (!p) return null;

  return (
    <div className="stack">
      <Link to="/products" className="muted">← Back to products</Link>

      <div className="card card-pad" style={{ display: "grid", gap: 24, gridTemplateColumns: "minmax(0,1fr) minmax(0,1.2fr)" }}>
        <div className="product-thumb" style={{ borderRadius: "var(--radius)", minHeight: 240 }}>
          <ProductImage imageUrl={p.image_url} name={p.name} critical />
        </div>
        <div className="stack">
          <div className="product-cat">{p.category}</div>
          <h1 style={{ margin: 0 }}>{p.name}</h1>
          <div className="row-wrap">
            <EcoScore score={p.eco_score} />
            {p.is_eco_friendly && <EcoBadge />}
            <StockBadge quantity={p.stock_quantity} threshold={p.low_stock_threshold} />
          </div>
          <p className="muted">{p.description}</p>
          <div className="panel">
            <div className="spread"><span>Estimated carbon impact</span>
              <strong className="mono">{p.carbon_factor.toFixed(2)} kg CO₂e<span className="muted"> / unit</span></strong></div>
            <div className="reason">Estimate based on this product's documented carbon factor.</div>
          </div>
          <div className="spread">
            <span className="price" style={{ fontSize: "1.6rem" }}>{money(p.price)}</span>
            <div className="row">
              <input type="number" min={1} max={p.stock_quantity} value={qty} className="input"
                style={{ width: 76 }} onChange={(e) => setQty(Math.max(1, Number(e.target.value)))} />
              <button className="btn btn-primary" onClick={add} disabled={p.stock_quantity <= 0}>
                Add to cart
              </button>
            </div>
          </div>
          {msg && <div className="alert alert-info">{msg}</div>}
        </div>
      </div>

      {p.eco_alternative && <EcoAlternative alt={p.eco_alternative} />}

      {p.recommendations.length > 0 && (
        <section className="stack">
          <h2>You might also like</h2>
          <div className="grid-products">
            {p.recommendations.map((r) => <RecoCard key={r.id} r={r} />)}
          </div>
        </section>
      )}
    </div>
  );
}

function EcoAlternative({ alt }: { alt: Recommendation }) {
  return (
    <section className="card card-pad eco-alt">
      <div className="row-wrap" style={{ justifyContent: "space-between" }}>
        <div>
          <span className="badge badge-eco">🌱 Greener alternative</span>
          <h2 style={{ margin: "10px 0 4px" }}>
            <Link to={`/products/${alt.id}`}>{alt.name}</Link>
          </h2>
          <div className="reason">{alt.reason}</div>
        </div>
        <div className="row"><EcoScore score={alt.eco_score} />
          <Link to={`/products/${alt.id}`} className="btn btn-accent btn-sm">View</Link></div>
      </div>
    </section>
  );
}

function RecoCard({ r }: { r: Recommendation }) {
  return (
    <Link to={`/products/${r.id}`} className="card product-card" style={{ color: "inherit" }}>
      <div className="product-thumb"><ProductImage imageUrl={r.image_url} name={r.name} /></div>
      <div className="product-body">
        <div className="product-name">{r.name}</div>
        <EcoScore score={r.eco_score} />
        <div className="reason">{r.reason}</div>
        <div className="price" style={{ marginTop: "auto" }}>{money(r.price)}</div>
      </div>
    </Link>
  );
}
