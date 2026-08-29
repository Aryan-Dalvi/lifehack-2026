import { useCallback, useEffect, useState } from "react";
import { MerchantAdmin } from "./features/merchant/MerchantAdmin";
import { MerchantDashboard } from "./features/merchant/MerchantDashboard";
import { ShopperApp } from "./features/shopper/ShopperApp";
import { LandingPage } from "./features/landing/LandingPage";

export function App() {
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const handlePopState = () => {
      setPath(window.location.pathname);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  // Stable identity: the dashboard holds this in an effect's dependency list, and a fresh
  // function on every render would refetch the whole report each time App re-renders.
  const navigate = useCallback((newPath: string) => {
    window.history.pushState({}, "", newPath);
    setPath(window.location.pathname);
  }, []);

  // Store setup is onboarding; /admin is where a merchant lands once it is done. The
  // dashboard sends a still-draft merchant back to setup after it reads their status.
  if (path.startsWith("/admin/setup")) {
    return <MerchantAdmin onNavigate={navigate} />;
  }

  if (path.startsWith("/admin")) {
    return <MerchantDashboard onNavigate={navigate} />;
  }

  if (path.startsWith("/storefront")) {
    return <ShopperApp />;
  }

  return <LandingPage onNavigate={navigate} />;
}

