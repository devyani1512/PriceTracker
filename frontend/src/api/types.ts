export interface User {
  id: number;
  email: string;
  displayName: string | null;
  createdAt: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface ProductCard {
  id: number;
  slug: string | null;
  name: string;
  brand: string | null;
  category: string | null;
  sku: string | null;
  description: string | null;
  structureChanged: boolean;
}

export interface Snapshot {
  id: string;
  productId: number;
  slotAt: string;
  bucketAt?: string | null;
  capturedAt: string;
  price: number | null;
  wasPrice: number | null;
  discountPct: number | null;
  currency: string | null;
  inStock: boolean | null;
  stockLabel: string | null;
  stockCount: number | null;
  trigger: string;
  structureChanged: boolean;
}

export interface Review {
  id: string;
  author: string;
  rating: number;
  title: string;
  body: string;
  date: string;
  verifiedPurchase: boolean;
  helpfulVotes: number;
}

export interface ProductDetail extends ProductCard {
  specs: Record<string, string | number>;
  reviews: Review[];
  detailLoaded: boolean;
  structureNote: string | null;
  latest: Snapshot | null;
  snapshotCount: number;
  pending: boolean;
}

export interface Tracker {
  id: string;
  productId: number;
  product: ProductCard | null;
  refreshMinutes: number;
  active: boolean;
  alertOnPriceDrop: boolean;
  priceDropThresholdPct: number | null;
  alertOnBackInStock: boolean;
  lastCoveredSlot: string | null;
  lastScrapedAt: string | null;
  createdAt: string;
  latest: Snapshot | null;
  snapshotCount: number;
}

export type ScrapeOutcome = "success" | "retried" | "failed";

export interface ScrapeLog {
  id: string;
  productId: number;
  productName: string | null;
  trackerId: string | null;
  attempt: number;
  outcome: ScrapeOutcome;
  errorKind: string | null;
  message: string | null;
  durationMs: number;
  price: number | null;
  inStock: boolean | null;
  createdAt: string;
}

export type NotificationType = "price_drop" | "back_in_stock";
export type NotificationStatus = "pending" | "sent" | "failed";

export interface Notification {
  id: string;
  userId: string;
  productId: number;
  trackerId: string | null;
  type: NotificationType;
  status: NotificationStatus;
  thresholdPct: number | null;
  title: string | null;
  message: string | null;
  error: string | null;
  createdAt: string;
  sentAt: string | null;
}

export interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  pages: number;
}

export interface CatalogStatus {
  count: number;
  expected: number;
  complete: boolean;
}

export interface HistoryStats {
  count: number;
  min: number | null;
  max: number | null;
  current: number | null;
  first: number | null;
  changePct: number | null;
}

export interface TrackerHistory {
  points: Snapshot[];
  stats: HistoryStats;
}

export interface DashboardStats {
  trackedProducts: number;
  activeTrackers: number;
  structureChanges: number;
  pendingAlerts: number;
  sentAlerts: number;
}

export interface Dashboard {
  stats: DashboardStats;
  trackers: Tracker[];
  notifications: Notification[];
  recentLogs: ScrapeLog[];
}

export interface AddTrackerInput {
  productId: number;
  refreshMinutes?: number;
  alertOnPriceDrop?: boolean;
  priceDropThresholdPct?: number;
  alertOnBackInStock?: boolean;
  runNow?: boolean;
}

export interface UpdateTrackerInput {
  refreshMinutes?: number;
  active?: boolean;
  alertOnPriceDrop?: boolean;
  priceDropThresholdPct?: number;
  alertOnBackInStock?: boolean;
}
