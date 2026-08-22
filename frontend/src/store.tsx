// App state: auth + cart-count contexts (Spec §17 — refresh on mutation, never poll).
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, tokenStore } from "./api";
import type { Customer } from "./types";

interface AppState {
  customer: Customer | null;
  loading: boolean;
  cartCount: number;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshCart: () => Promise<void>;
}

const Ctx = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(true);
  const [cartCount, setCartCount] = useState(0);

  const refreshCart = useCallback(async () => {
    if (!tokenStore.get()) { setCartCount(0); return; }
    try {
      const cart = await api.cart();
      setCartCount(cart.item_count);
    } catch { setCartCount(0); }
  }, []);

  // On first load: if a token exists, resolve the customer once (no polling).
  useEffect(() => {
    (async () => {
      if (tokenStore.get()) {
        try {
          setCustomer(await api.me());
          await refreshCart();
        } catch (e) {
          if (e instanceof ApiError && e.status === 401) tokenStore.clear();
        }
      }
      setLoading(false);
    })();
  }, [refreshCart]);

  const afterAuth = useCallback(async (token: string) => {
    tokenStore.set(token);
    setCustomer(await api.me());
    await refreshCart();
  }, [refreshCart]);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.login(email, password);
    await afterAuth(access_token);
  }, [afterAuth]);

  const register = useCallback(async (name: string, email: string, password: string) => {
    const { access_token } = await api.register(name, email, password);
    await afterAuth(access_token);
  }, [afterAuth]);

  const logout = useCallback(() => {
    tokenStore.clear();       // stateless JWT: client-side discard is the whole logout (Spec §6)
    setCustomer(null);
    setCartCount(0);
  }, []);

  return (
    <Ctx.Provider value={{ customer, loading, cartCount, login, register, logout, refreshCart }}>
      {children}
    </Ctx.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useApp(): AppState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
