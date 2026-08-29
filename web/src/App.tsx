import { MerchantAdmin } from "./features/merchant/MerchantAdmin";
import { ShopperApp } from "./features/shopper/ShopperApp";

export function App() {
  const path = window.location.pathname;
  return path.startsWith("/admin") ? <MerchantAdmin /> : <ShopperApp />;
}

