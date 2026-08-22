import { StrictMode, lazy, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./index.css";
import "./App.css";
import App from "./App";
import { AppProvider } from "./store";
import { Spinner } from "./components";
import { RequireAdmin, RequireAuth } from "./guards";

// Customer pages — eager (the common path).
import Products from "./pages/Products";
import ProductDetail from "./pages/ProductDetail";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Cart from "./pages/Cart";
import Checkout from "./pages/Checkout";
import OrderConfirmation from "./pages/OrderConfirmation";
import Orders from "./pages/Orders";
import NotFound from "./pages/NotFound";

// Admin pages + charts — lazy so Recharts ships only to admins (Spec §18 code-splitting).
const AdminDashboard = lazy(() => import("./pages/admin/AdminDashboard"));
const AdminProducts = lazy(() => import("./pages/admin/AdminProducts"));
const AdminOrders = lazy(() => import("./pages/admin/AdminOrders"));
const AdminReports = lazy(() => import("./pages/admin/AdminReports"));

const lazyPage = (el: React.ReactNode) => <Suspense fallback={<Spinner />}>{el}</Suspense>;

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Products /> },
      { path: "products", element: <Products /> },
      { path: "products/:id", element: <ProductDetail /> },
      { path: "login", element: <Login /> },
      { path: "register", element: <Register /> },
      { path: "cart", element: <Cart /> },
      { path: "checkout", element: <RequireAuth><Checkout /></RequireAuth> },
      { path: "orders", element: <RequireAuth><Orders /></RequireAuth> },
      { path: "orders/:id", element: <RequireAuth><OrderConfirmation /></RequireAuth> },
      { path: "admin", element: <RequireAdmin>{lazyPage(<AdminDashboard />)}</RequireAdmin> },
      { path: "admin/products", element: <RequireAdmin>{lazyPage(<AdminProducts />)}</RequireAdmin> },
      { path: "admin/orders", element: <RequireAdmin>{lazyPage(<AdminOrders />)}</RequireAdmin> },
      { path: "admin/reports", element: <RequireAdmin>{lazyPage(<AdminReports />)}</RequireAdmin> },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProvider>
      <RouterProvider router={router} />
    </AppProvider>
  </StrictMode>,
);
