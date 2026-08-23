// Small reusable presentational components (Spec §30 — reusable, no duplication).
import { Link } from "react-router-dom";
import type { ProductSummary } from "./types";
import { ProductImage } from "./productImage";

export function Leaf({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 20c0-8 6-14 16-16-1 10-6 16-14 16-1 0-2 0-2 0Z" fill="currentColor" opacity="0.9" />
      <path d="M6 18C10 12 14 9 18 8" stroke="#fff" strokeWidth="1.4" strokeLinecap="round" opacity="0.7" />
    </svg>
  );
}

export function EcoScore({ score }: { score: number }) {
  return (
    <span className="eco-meter" title={`Eco score ${score}/100`}>
      <span className="eco-bar"><span style={{ width: `${score}%` }} /></span>
      <span className="muted" style={{ fontSize: "0.8rem" }}>{score}</span>
    </span>
  );
}

export function StockBadge({ quantity, threshold }: { quantity: number; threshold?: number }) {
  if (quantity <= 0) return <span className="badge badge-danger">Out of stock</span>;
  if (threshold !== undefined && quantity <= threshold)
    return <span className="badge badge-warn">Low stock · {quantity}</span>;
  return <span className="badge badge-neutral">In stock</span>;
}

export function EcoBadge() {
  return <span className="badge badge-eco">🌱 Eco-friendly</span>;
}

export function Spinner() {
  return <div className="loading"><div className="spinner" aria-label="Loading" /></div>;
}

export function ErrorNote({ message }: { message: string }) {
  return <div className="alert alert-error" role="alert">{message}</div>;
}

export function ConfirmModal({ title, message, confirmLabel, onConfirm, onCancel }: {
  title: string; message: string; confirmLabel: string; onConfirm: () => void; onCancel: () => void;
}) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={onCancel}>
    <div className="modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title" onMouseDown={(event) => event.stopPropagation()}>
      <h2 id="confirm-title">{title}</h2>
      <p className="muted">{message}</p>
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
        <button className="btn btn-primary" onClick={onConfirm}>{confirmLabel}</button>
      </div>
    </div>
  </div>;
}

const money = (n: number) => `₦${n.toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
export { money };

export function ProductCard({ p }: { p: ProductSummary }) {
  return (
    <Link to={`/products/${p.id}`} className="card product-card" style={{ color: "inherit" }}>
      <div className="product-thumb"><ProductImage imageUrl={p.image_url} name={p.name} /></div>
      <div className="product-body">
        <div className="product-cat">{p.category}</div>
        <div className="product-name">{p.name}</div>
        <div className="row-wrap" style={{ gap: 6 }}>
          <EcoScore score={p.eco_score} />
          {p.is_eco_friendly && <EcoBadge />}
        </div>
        <div className="spread" style={{ marginTop: "auto" }}>
          <span className="price">{money(p.price)}</span>
          <StockBadge quantity={p.stock_quantity} />
        </div>
      </div>
    </Link>
  );
}
