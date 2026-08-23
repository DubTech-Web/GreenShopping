// Shared API types — mirror the backend Pydantic DTOs (Spec §30 typed frontend).

export interface TokenResponse { access_token: string; token_type: string; }
export interface MessageResponse { message: string; dev_code?: string | null; cooldown_seconds?: number | null; }
export interface Customer { id: number; name: string; email: string; is_admin: boolean; is_verified: boolean; created_at: string; }

export interface ProductSummary {
  id: number; name: string; image_url: string; category: string; price: number;
  stock_quantity: number; eco_score: number; is_eco_friendly: boolean;
}
export interface Recommendation extends ProductSummary {
  carbon_factor: number; score: number; reason: string;
}
export interface ProductDetail extends ProductSummary {
  description: string; weight: number; carbon_factor: number; low_stock_threshold: number;
  recommendations: Recommendation[]; eco_alternative: Recommendation | null;
}
export interface PageMeta { page: number; limit: number; total: number; pages: number; }
export interface ProductPage { items: ProductSummary[]; meta: PageMeta; }

export interface CartItem {
  id: number; product_id: number; name: string; price: number;
  quantity: number; stock_quantity: number; line_total: number;
}
export interface Cart { items: CartItem[]; subtotal: number; item_count: number; }

export interface DeliveryOptionEstimate {
  key: string; label: string; speed: string; cost: number;
  emission_factor: number; delivery_carbon: number; total_carbon: number;
}
export interface Estimate {
  product_carbon: number; package_weight: number; options: DeliveryOptionEstimate[];
  recommended: string; reason: string; unit: string; is_estimate: boolean;
}

export interface OrderItem {
  product_id: number; name: string; quantity: number; unit_price: number; line_total: number;
}
export interface Order {
  id: number; status: string; total_amount: number; delivery_method: string;
  delivery_distance: number; carbon_impact: number; created_at: string; items: OrderItem[];
}
export interface OrderSummary {
  id: number; status: string; total_amount: number; delivery_method: string;
  carbon_impact: number; created_at: string;
}

// Admin
export interface AdminProductRow {
  id: number; name: string; category: string; price: number; stock_quantity: number;
  low_stock_threshold: number; eco_score: number; is_eco_friendly: boolean; stock_status: string;
}
export interface AdminOrderRow {
  id: number; customer_id: number; status: string; total_amount: number;
  delivery_method: string; carbon_impact: number; created_at: string;
}
export interface RestockRow {
  product_id: number; name: string; stock_quantity: number; low_stock_threshold: number;
  recent_units_sold: number; status: string; suggested_reorder_qty: number; reason: string;
}
export interface Dashboard {
  total_sales: number; total_orders: number; total_products: number;
  low_stock_products: number; eco_delivery_percentage: number; total_estimated_co2: number;
}
export interface BestSeller { product_id: number; name: string; units_sold: number; revenue: number; }
export interface NamedValue { name: string; value: number; }
export interface SalesReport {
  total_sales: number; total_orders: number; best_sellers: BestSeller[]; sales_by_category: NamedValue[];
}
export interface SustainabilityReport {
  total_estimated_co2: number; average_co2_per_order: number; eco_delivery_count: number;
  eco_delivery_percentage: number; eco_products_sold_units: number;
  estimated_co2_saved_vs_express: number; unit: string; is_estimate: boolean;
}

export interface PaymentInit {
  reference: string; amount_kobo: number; public_key: string; email: string;
  simulated: boolean; authorization_url?: string | null; access_code?: string | null;
}
