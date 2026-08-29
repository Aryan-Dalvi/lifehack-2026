import { useState, useEffect } from "react";
import { MerchantAdmin } from "./features/merchant/MerchantAdmin";
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

  const navigate = (newPath: string) => {
    window.history.pushState({}, "", newPath);
    setPath(window.location.pathname);
  };

  if (path.startsWith("/admin")) {
    return <MerchantAdmin />;
  }

  if (path.startsWith("/storefront")) {
    return <ShopperApp />;
  }

  return <LandingPage onNavigate={navigate} />;
}

