import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { ProductSummary } from "../types";
import { ProductCard } from "../components";
import { ProductImage } from "../productImage";

export default function Landing() {
  const [featured, setFeatured] = useState<ProductSummary[]>([]);

  useEffect(() => { api.products({ limit: 4 }).then((data) => setFeatured(data.items)).catch(() => {}); }, []);

  return (
    <div className="landing stack">
      <section className="landing-hero">
        <div className="landing-copy">
          <span className="eyebrow">Thoughtful shopping, lighter footprints</span>
          <h1>Good choices,<br /><em>made visible.</em></h1>
          <p>Discover useful everyday products, understand their estimated impact, and choose delivery that is kinder to the air we share.</p>
          <div className="row-wrap">
            <Link to="/products" className="btn btn-accent">Explore the collection</Link>
            <a href="#how-it-works" className="landing-link">How it works ↓</a>
          </div>
        </div>
        <div className="landing-feature">
          {featured[0] && <ProductImage imageUrl={featured[0].image_url} name={featured[0].name} critical />}
          <div className="landing-stamp"><strong>01</strong><span>Choose<br />with context</span></div>
        </div>
      </section>

      <section id="how-it-works" className="landing-principles">
        <div><span className="eyebrow">The GreenShopping method</span><h2>A clearer path from want to worth.</h2></div>
        <div className="principle-grid">
          <article><span>01</span><h3>See the difference</h3><p>Every item carries an explainable eco score and a transparent carbon estimate.</p></article>
          <article><span>02</span><h3>Meet your match</h3><p>Local recommendations surface useful alternatives with better sustainability signals.</p></article>
          <article><span>03</span><h3>Send it wisely</h3><p>Compare delivery impact before checkout and choose the lower-emission route.</p></article>
        </div>
      </section>

      <section className="landing-featured">
        <div className="spread"><div><span className="eyebrow">A considered edit</span><h2>Small upgrades, real utility.</h2></div><Link to="/products" className="landing-link">View all products →</Link></div>
        <div className="grid-products">{featured.slice(1).map((product) => <ProductCard key={product.id} p={product} />)}</div>
      </section>
    </div>
  );
}
