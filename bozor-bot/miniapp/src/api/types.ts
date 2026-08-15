export type PhotoOut = { thumb: string; full: string; width?: number; height?: number };

export type Card = {
  public_id: string;
  category: string;
  title: string;
  price: number;
  currency: string;
  is_negotiable: boolean;
  city?: string | null;
  district?: string | null;
  status: string;
  published_at?: string | null;
  photos: PhotoOut[];
  lat?: number | null;
  lon?: number | null;
  reject_reason?: string | null;
  is_rent?: boolean;
};

export type Spec = { key: string; label: string; value: string; unit?: string | null; verified?: boolean };

export type ListingDetail = Card & {
  description: string;
  specs: Spec[];
  views_count: number;
  address?: string | null;
  is_owner: boolean;
};

export type FieldOut = {
  key: string; label: string; type: string;
  required: boolean; stored: string;
  min?: number | null; max?: number | null; max_len?: number | null;
  options?: [string, string][] | null;
  options_ref?: string | null; depends_on?: string | null;
  allow_other?: boolean;
  visible_if?: Record<string, string[]> | null;
  filter: 'range' | 'multiselect' | 'checkbox' | 'exact' | 'none';
  unit?: string | null; hint?: string | null;
  identifier?: string | null;
};

export type SchemaOut = {
  slug: string; parent: string; title: string; emoji: string;
  is_rent: boolean; fields: FieldOut[];
};

export type CategoryNode = { slug: string; title: string; emoji: string; is_rent: boolean };
export type Direction = { slug: string; title: string; emoji: string; categories: CategoryNode[] };

export type UserOut = { id: number; tg_id: number; username?: string | null; first_name: string; is_admin: boolean };

export type PublicConfig = {
  bot_username: string;
  bot_link: string | null;
  uploads_enabled: boolean;
  max_photos: number;
  currencies: string[];
};
