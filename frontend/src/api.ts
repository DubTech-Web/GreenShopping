// Typed API client (Spec §17, §26). One thin fetch wrapper; attaches the JWT and extracts
// FastAPI error details. No axios — native fetch keeps the bundle small (Spec §18).
import type {
  AdminOrderRow, AdminProductRow, Cart, Customer, Dashboard, Estimate, Order, OrderSummary,
  ProductDetail, ProductPage, RestockRow, SalesReport, SustainabilityReport, TokenResponse,
  MessageResponse, PaymentInit,
} from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";
const TOKEN_KEY = "greenshopping_token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = tokenStore.get();
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
  if (options.body) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (res.status === 204) return undefined as T;

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    // FastAPI returns {detail: string} or {detail: [{msg}]}; normalize to one message.
    const detail = data?.detail;
    const message = Array.isArray(detail) ? detail[0]?.msg ?? "Request failed"
      : typeof detail === "string" ? detail : "Request failed";
    throw new ApiError(res.status, message);
  }
  return data as T;
}

const body = (v: unknown) => JSON.stringify(v);

export const api = {
  // Auth
  register: (name: string, email: string, password: string) =>
    request<MessageResponse>("/api/auth/register", { method: "POST", body: body({ name, email, password }) }),
  verifyEmail: (email: string, code: string) =>
    request<TokenResponse>("/api/auth/verify-email", { method: "POST", body: body({ email, code }) }),
  resendCode: (email: string) =>
    request<MessageResponse>("/api/auth/resend-code", { method: "POST", body: body({ email }) }),
  forgotPassword: (email: string) =>
    request<MessageResponse>("/api/auth/forgot-password", { method: "POST", body: body({ email }) }),
  resetPassword: (email: string, code: string, new_password: string) =>
    request<MessageResponse>("/api/auth/reset-password", { method: "POST", body: body({ email, code, new_password }) }),
  login: (email: string, password: string) =>
    request<TokenResponse>("/api/auth/login", { method: "POST", body: body({ email, password }) }),
  me: () => request<Customer>("/api/auth/me"),
  updateProfile: (name: string) =>
    request<Customer>("/api/auth/me", { method: "PATCH", body: body({ name }) }),

  // Products
  products: (params: { page?: number; limit?: number; category?: string; eco_only?: boolean; q?: string } = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== "" && v !== false) qs.set(k, String(v)); });
    return request<ProductPage>(`/api/products?${qs.toString()}`);
  },
  product: (id: number) => request<ProductDetail>(`/api/products/${id}`),
  categories: () => request<string[]>("/api/products/meta/categories"),

  // Cart
  cart: () => request<Cart>("/api/cart"),
  addToCart: (product_id: number, quantity: number) =>
    request<Cart>("/api/cart/items", { method: "POST", body: body({ product_id, quantity }) }),
  updateCartItem: (id: number, quantity: number) =>
    request<Cart>(`/api/cart/items/${id}`, { method: "PATCH", body: body({ quantity }) }),
  removeCartItem: (id: number) => request<Cart>(`/api/cart/items/${id}`, { method: "DELETE" }),

  // Carbon estimate (single call powers the checkout impact panel)
  estimate: (delivery_distance: number) =>
    request<Estimate>("/api/carbon/estimate", { method: "POST", body: body({ delivery_distance }) }),

  // Orders
  checkout: (delivery_method: string, delivery_distance: number) =>
    request<Order>("/api/orders", { method: "POST", body: body({ delivery_method, delivery_distance }) }),
  initPayment: (order_id: number, callback_url?: string) =>
    request<PaymentInit>("/api/payments/init", { method: "POST", body: body({ order_id, callback_url }) }),
  verifyPayment: (reference: string) =>
    request<Order>("/api/payments/verify", { method: "POST", body: body({ reference }) }),
  orders: () => request<OrderSummary[]>("/api/orders"),
  order: (id: number) => request<Order>(`/api/orders/${id}`),
  cancelOrder: (id: number) => request<Order>(`/api/orders/${id}/cancel`, { method: "POST" }),

  // Admin
  adminProducts: (page = 1, limit = 50) =>
    request<{ items: AdminProductRow[]; meta: unknown }>(`/api/admin/products?page=${page}&limit=${limit}`),
  updateProduct: (id: number, patch: Partial<AdminProductRow>) =>
    request<AdminProductRow>(`/api/admin/products/${id}`, { method: "PATCH", body: body(patch) }),
  restock: () => request<RestockRow[]>("/api/admin/inventory/restock"),
  adminOrders: (page = 1, limit = 50) =>
    request<{ items: AdminOrderRow[]; meta: unknown }>(`/api/admin/orders?page=${page}&limit=${limit}`),
  updateOrderStatus: (id: number, status: string) =>
    request<AdminOrderRow>(`/api/admin/orders/${id}`, { method: "PATCH", body: body({ status }) }),

  // Reports
  dashboard: () => request<Dashboard>("/api/reports/dashboard"),
  salesReport: () => request<SalesReport>("/api/reports/sales"),
  sustainabilityReport: () => request<SustainabilityReport>("/api/reports/sustainability"),
};
