import { request } from "./client";
import type {
  AddTrackerInput,
  AuthResponse,
  CatalogStatus,
  Dashboard,
  Notification,
  Paged,
  ProductCard,
  ProductDetail,
  ScrapeLog,
  Tracker,
  TrackerHistory,
  UpdateTrackerInput,
  User,
} from "./types";

export * from "./types";
export {
  ApiError,
  API_URL,
  clearToken,
  errorMessage,
  getToken,
  setToken,
} from "./client";

export const authApi = {
  register(body: {
    email: string;
    password: string;
    displayName?: string;
  }): Promise<AuthResponse> {
    return request<AuthResponse>("POST", "/user/register", { body });
  },
  login(body: { email: string; password: string }): Promise<AuthResponse> {
    return request<AuthResponse>("POST", "/user/login", { body });
  },
  async me(): Promise<User> {
    const res = await request<{ user: User }>("GET", "/user/me");
    return res.user;
  },
};

export const productApi = {
  search(q: string, page = 1, pageSize = 12): Promise<Paged<ProductCard>> {
    return request<Paged<ProductCard>>("GET", "/product/search", {
      query: { q, page, pageSize },
    });
  },
  list(page = 1, pageSize = 12): Promise<Paged<ProductCard>> {
    return request<Paged<ProductCard>>("GET", "/product/list", {
      query: { page, pageSize },
    });
  },
  get(id: number | string, ensurePrice = false): Promise<ProductDetail> {
    return request<ProductDetail>("GET", `/product/${id}`, {
      query: { ensurePrice },
    });
  },
  refresh(id: number | string, wait = false): Promise<{ status: string }> {
    return request<{ status: string }>("POST", `/product/${id}/refresh`, {
      query: { wait },
    });
  },
  logs(
    id: number | string,
    limit = 20,
    page = 1,
  ): Promise<Paged<ScrapeLog>> {
    return request<Paged<ScrapeLog>>("GET", `/product/${id}/logs`, {
      query: { limit, page },
    });
  },
  catalogStatus(): Promise<CatalogStatus> {
    return request<CatalogStatus>("GET", "/catalog/status");
  },
};

export const trackerApi = {
  add(body: AddTrackerInput): Promise<Tracker> {
    return request<Tracker>("POST", "/tracker/add", { body });
  },
  async list(): Promise<Tracker[]> {
    const res = await request<{ items: Tracker[] }>("GET", "/tracker/list");
    return res.items ?? [];
  },
  get(id: string): Promise<Tracker> {
    return request<Tracker>("GET", `/tracker/${id}`);
  },
  update(id: string, body: UpdateTrackerInput): Promise<Tracker> {
    return request<Tracker>("PATCH", `/tracker/${id}`, { body });
  },
  remove(id: string): Promise<{ status: string }> {
    return request<{ status: string }>("DELETE", `/tracker/${id}`);
  },
  history(id: string, days = 30): Promise<TrackerHistory> {
    return request<TrackerHistory>("GET", `/tracker/${id}/history`, {
      query: { days },
    });
  },
  logs(id: string, limit = 20, page = 1): Promise<Paged<ScrapeLog>> {
    return request<Paged<ScrapeLog>>("GET", `/tracker/${id}/logs`, {
      query: { limit, page },
    });
  },
};

export const dashboardApi = {
  get(): Promise<Dashboard> {
    return request<Dashboard>("GET", "/dashboard");
  },
};

export const notificationApi = {
  subscribe(body: {
    productId: number;
    trackerId?: string;
  }): Promise<Notification> {
    return request<Notification>("POST", "/notification/subscribe", { body });
  },
  async list(): Promise<Notification[]> {
    const res = await request<{ items: Notification[] }>(
      "GET",
      "/notification/list",
    );
    return res.items ?? [];
  },
};
