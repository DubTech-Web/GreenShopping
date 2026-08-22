// Product imagery as inline SVG illustrations (Spec §18 optimized assets, §29 no deps).
// One line-art icon per category, drawn in `currentColor` so it themes with .product-thumb
// (moss in light, leaf in dark). Zero network requests, zero API payload — the image is
// derived from the product's category on the client.
import type { JSX } from "react";

const ICONS: Record<string, JSX.Element> = {
  Drinkware: (
    <>
      <rect x="92" y="22" width="16" height="10" rx="2" />
      <path d="M88 32 h24 v6 l6 12 v58 a6 6 0 0 1-6 6 H88 a6 6 0 0 1-6-6 V50 l6-12 z" />
      <line x1="82" y1="72" x2="118" y2="72" />
    </>
  ),
  Bags: (
    <>
      <path d="M70 56 h60 l-6 62 a6 6 0 0 1-6 6 H82 a6 6 0 0 1-6-6 z" />
      <path d="M86 56 a14 14 0 0 1 28 0" />
    </>
  ),
  Kitchen: (
    <>
      <rect x="72" y="60" width="56" height="46" rx="7" />
      <line x1="64" y1="74" x2="72" y2="74" />
      <line x1="128" y1="74" x2="136" y2="74" />
      <line x1="80" y1="52" x2="120" y2="52" />
      <line x1="100" y1="44" x2="100" y2="52" />
    </>
  ),
  "Personal Care": (
    <>
      <rect x="84" y="58" width="32" height="58" rx="7" />
      <rect x="94" y="42" width="12" height="16" />
      <path d="M94 42 h-12 v-8 h18" />
    </>
  ),
  Home: (
    <>
      <path d="M58 80 l42-34 l42 34" />
      <path d="M70 76 v42 h60 v-42" />
      <rect x="92" y="94" width="16" height="24" />
    </>
  ),
  Stationery: (
    <>
      <path d="M66 116 l46-46 l16 16 l-46 46 l-22 6 z" />
      <line x1="104" y1="78" x2="120" y2="94" />
      <line x1="72" y1="110" x2="88" y2="126" />
    </>
  ),
  Electronics: (
    <>
      <rect x="80" y="32" width="40" height="76" rx="9" />
      <line x1="92" y1="40" x2="108" y2="40" />
      <circle cx="100" cy="98" r="3" />
    </>
  ),
};

const FALLBACK = (
  <>
    <rect x="72" y="58" width="56" height="46" rx="4" />
    <path d="M72 74 h56" />
    <path d="M100 58 v46" />
  </>
);

export function ProductImage({ category, ecoFriendly }: { category: string; ecoFriendly?: boolean }) {
  return (
    <svg viewBox="0 0 200 150" width="100%" height="100%" role="img"
      aria-label={`${category} product illustration`} preserveAspectRatio="xMidYMid meet"
      fill="none" stroke="currentColor" strokeWidth={5} strokeLinecap="round" strokeLinejoin="round">
      {ICONS[category] ?? FALLBACK}
      {ecoFriendly && (
        // Small eco leaf accent, bottom-right.
        <g stroke="none" fill="var(--eco)">
          <path d="M150 118c0-14 10-24 26-26-1 16-11 26-24 26z" opacity="0.9" />
        </g>
      )}
    </svg>
  );
}
