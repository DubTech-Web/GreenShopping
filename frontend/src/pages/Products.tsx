import { useEffect, useState } from "react";
import { api } from "../api";
import type { ProductPage } from "../types";
import { ErrorNote, ProductCard, Spinner } from "../components";

export default function Products() {
  const [data, setData] = useState<ProductPage | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState("");
  const [ecoOnly, setEcoOnly] = useState(false);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // Categories are static reference data — fetched once, then reused (Spec §17).
  useEffect(() => { api.categories().then(setCategories).catch(() => {}); }, []);

  // One request per filter/page change. No refetch on unrelated re-renders (Spec §17).
  useEffect(() => {
    let active = true;
    setLoading(true);
    api.products({ page, limit: 12, category, eco_only: ecoOnly, q })
      .then((d) => { if (active) { setData(d); setError(""); } })
      .catch((e) => { if (active) setError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [page, category, ecoOnly, q]);

  const resetTo = (fn: () => void) => { fn(); setPage(1); };

  return (
    <div className="stack">
      <section className="hero-band">
        <h1>Shop sustainably 🌿</h1>
        <p>Every product shows its eco score and estimated carbon impact. We recommend greener
          alternatives and lower-emission delivery — so you can shop with the planet in mind.</p>
      </section>

      <div className="card card-pad">
        <div className="row-wrap">
          <div className="field grow">
            <label className="label" htmlFor="q">Search</label>
            <input id="q" className="input" placeholder="Search products…" value={q}
              onChange={(e) => resetTo(() => setQ(e.target.value))} />
          </div>
          <div className="field">
            <label className="label" htmlFor="cat">Category</label>
            <select id="cat" className="select" value={category}
              onChange={(e) => resetTo(() => setCategory(e.target.value))}>
              <option value="">All categories</option>
              {categories.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <label className="row" style={{ gap: 8, marginTop: 22, cursor: "pointer" }}>
            <input type="checkbox" checked={ecoOnly}
              onChange={(e) => resetTo(() => setEcoOnly(e.target.checked))} />
            <span className="label" style={{ margin: 0 }}>Eco-friendly only</span>
          </label>
        </div>
      </div>

      {error && <ErrorNote message={error} />}
      {loading ? <Spinner /> : data && (
        <>
          <div className="spread">
            <span className="muted">{data.meta.total} products</span>
          </div>
          {data.items.length === 0 ? (
            <div className="panel center-text">No products match your filters.</div>
          ) : (
            <div className="grid-products">
              {data.items.map((p) => <ProductCard key={p.id} p={p} />)}
            </div>
          )}

          {data.meta.pages > 1 && (
            <div className="row" style={{ justifyContent: "center", marginTop: 12 }}>
              <button className="btn btn-ghost btn-sm" disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}>← Prev</button>
              <span className="muted mono">Page {data.meta.page} of {data.meta.pages}</span>
              <button className="btn btn-ghost btn-sm" disabled={page >= data.meta.pages}
                onClick={() => setPage((p) => p + 1)}>Next →</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
