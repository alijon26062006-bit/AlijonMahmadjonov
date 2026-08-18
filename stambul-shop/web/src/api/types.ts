export type Card = {
  id: string;
  category: string;
  title: string;
  brand: string | null;
  price: number;
  old_price: number | null;
  status: string;
  in_stock: number;
  sizes: string[];
  photo: string | null;
};

export type VariantOut = {
  id: number; size: string; color: string; label: string;
  price: number; stock: number;
};

export type ProductDetail = Card & {
  description: string;
  category_title: string;
  photos: { full: string; thumb: string }[];
  specs: { label: string; value: string; unit: string | null }[];
  views_count: number;
  variants: VariantOut[];
};

export type CartOut = {
  items: {
    variant_id: number; product_id: string; title: string; variant: string;
    price: number; qty: number; available: number; line_total: number;
    photo: string | null;
  }[];
  goods_total: number;
  count: number;
  issues: string[];
};

export type OrderOut = {
  id: number; public_id: string; number: number;
  status: string; status_label: string; next_statuses: string[];
  customer_name: string; phone: string; city: string | null;
  address: string | null; delivery: string; delivery_label: string;
  comment: string | null;
  goods_total: number; delivery_price: number; total: number;
  tracking: string | null; created_at: string | null;
  items: { title: string; variant: string; price: number; qty: number;
           line_total: number }[];
  payment?: { phone: string; name: string; link: string } | null;
};

export type ShopConfig = {
  shop_name: string;
  tagline: string;
  currency_sign: string;
  bot_link: string | null;
  support: string | null;
  uploads_enabled: boolean;
  max_photos: number;
  delivery: {
    city_price: number; country_price: number;
    free_from: number; pickup_address: string;
  };
  payment_ready: boolean;
  google_client_id: string;
  require_auth_to_browse: boolean;
  site_url: string;
  cities: { id: number; name: string; days: number }[];
};

export type FieldOut = {
  key: string; label: string; type: string; required: boolean;
  options: string[] | null; filter: string; unit: string | null;
  hint: string | null;
};

export type CategorySchema = {
  slug: string; title: string; group: string; icon: string;
  size_scales: { title: string; sizes: string[] }[];
  colors: string[];
  fields: FieldOut[];
};

export type Group = {
  title: string;
  categories: { slug: string; title: string; icon: string }[];
};

export type AdminProduct = Card & {
  photos_count: number;
  sales_count: number;
  variants: { id: number; size: string; color: string; price: number;
              stock: number; sku: string | null }[];
};

export type UserOut = {
  id: number;
  name: string;
  avatar_url: string | null;
  phone: string | null;
  email: string | null;
  tg_linked: boolean;
  city_id: number | null;
  address: string | null;
  notify_email: boolean;
  notify_telegram: boolean;
  onboarding_done: boolean;
  is_admin: boolean;
};
