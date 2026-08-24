import { useState } from "react";

export function ProductImage({ imageUrl, name, critical = false }: {
  imageUrl: string; name: string; critical?: boolean;
}) {
  const [error, setError] = useState(false);

  if (!imageUrl || error) {
    return (
      <div className="product-image-fallback" title={name} aria-label={name}>
        <span className="product-fallback-icon">🌿</span>
        <span className="product-fallback-name">{name}</span>
      </div>
    );
  }

  return (
    <img
      className="product-image"
      src={imageUrl}
      alt={name}
      width="640"
      height="480"
      loading={critical ? "eager" : "lazy"}
      decoding="async"
      onError={() => setError(true)}
    />
  );
}
