// App shell: header nav + footer, with <Outlet/> for routed pages.
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useApp } from "./store";
import { Leaf } from "./components";

export default function App() {
  const { customer, cartCount, logout } = useApp();
  const navigate = useNavigate();

  const onLogout = () => { logout(); navigate("/"); };

  return (
    <>
      <header className="appbar">
        <div className="container">
          <Link to="/" className="brand"><Leaf className="brand-leaf" /> GreenShopping</Link>
          <nav className="navlinks">
            <NavLink to="/products" className="navlink">Products</NavLink>
            <NavLink to="/cart" className="navlink">
              Cart{cartCount > 0 && <span className="cart-pill">{cartCount}</span>}
            </NavLink>
            {customer ? (
              <>
                <NavLink to="/orders" className="navlink">Orders</NavLink>
                {customer.is_admin && <NavLink to="/admin" className="navlink">Admin</NavLink>}
                <button className="btn btn-ghost btn-sm" onClick={onLogout}>Log out</button>
              </>
            ) : (
              <>
                <NavLink to="/login" className="navlink">Log in</NavLink>
                <NavLink to="/register" className="btn btn-accent btn-sm">Sign up</NavLink>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="container page">
        <Outlet />
      </main>

      <footer className="footer">
        <div className="container">
          GreenShopping — a Green Software Engineering demo. Carbon figures are estimates (kg CO₂e).
        </div>
      </footer>
    </>
  );
}
