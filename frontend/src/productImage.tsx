export function ProductImage({ imageUrl, name, critical = false }: {
  imageUrl: string; name: string; critical?: boolean;
}) {
  return <img className="product-image" src={imageUrl} alt={name}
    width="640" height="480" loading={critical ? "eager" : "lazy"} decoding="async" />;
}
