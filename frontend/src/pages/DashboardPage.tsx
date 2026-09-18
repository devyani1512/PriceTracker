import { useState } from "react";
import { Link } from "react-router-dom";
import { dashboardApi, productApi, trackerApi } from "../api";
import type { Tracker } from "../api";
import { useAsync } from "../hooks/useAsync";
import { errorMessage } from "../lib/utils";
import {
  formatCurrency,
  formatRefresh,
  formatRelative,
} from "../lib/format";
import { LogTable } from "../components/LogTable";
import {
  Button,
  EmptyState,
  InlineError,
  NotificationStatusBadge,
  NotificationTypeBadge,
  PageHeader,
  Panel,
  SectionLabel,
  SkeletonRows,
  StatCard,
  StockBadge,
} from "../components/ui";

export function DashboardPage() {
  const { data, loading, error, reload } = useAsync(() => dashboardApi.get(), []);
  const [busy, setBusy] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  async function handleRefresh(tracker: Tracker) {
    setBusy(`refresh-${tracker.id}`);
    setRowError(null);
    try {
      await productApi.refresh(tracker.productId, false);
      setTimeout(reload, 1200);
    } catch (err) {
      setRowError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleUntrack(tracker: Tracker) {
    setBusy(`untrack-${tracker.id}`);
    setRowError(null);
    try {
      await trackerApi.remove(tracker.id);
      setConfirmId(null);
      reload();
    } catch (err) {
      setRowError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  const stats = data?.stats;

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="Your tracked products, recent activity, and alerts."
        action={
          <Button variant="secondary" onClick={reload} loading={loading}>
            Refresh
          </Button>
        }
      />

      {rowError ? <InlineError className="mb-4">{rowError}</InlineError> : null}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatCard
          label="Tracked products"
          value={loading && !data ? "—" : (stats?.trackedProducts ?? 0)}
        />
        <StatCard
          label="Active trackers"
          value={loading && !data ? "—" : (stats?.activeTrackers ?? 0)}
        />
        <StatCard
          label="Structure changes"
          value={loading && !data ? "—" : (stats?.structureChanges ?? 0)}
        />
        <StatCard
          label="Pending alerts"
          value={loading && !data ? "—" : (stats?.pendingAlerts ?? 0)}
        />
        <StatCard
          label="Sent alerts"
          value={loading && !data ? "—" : (stats?.sentAlerts ?? 0)}
        />
      </div>

      {error ? <InlineError className="mt-4">{error}</InlineError> : null}

      <div className="mt-6">
        <Panel
          title="Tracked products"
          action={
            <Link
              to="/browse"
              className="text-[12px] text-ink-secondary hover:text-ink hover:underline"
            >
              Browse catalog
            </Link>
          }
          bodyClassName="p-0"
        >
          {loading && !data ? (
            <div className="p-4">
              <SkeletonRows rows={4} />
            </div>
          ) : !data || data.trackers.length === 0 ? (
            <div className="p-4">
              <EmptyState
                title="No tracked products yet"
                description="Browse the catalog and track a product to start collecting prices."
                action={
                  <Link to="/browse">
                    <Button variant="primary" size="sm">
                      Browse products
                    </Button>
                  </Link>
                }
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-[12px]">
                <thead>
                  <tr className="border-b border-line text-left text-[11px] uppercase tracking-wide text-ink-faint">
                    <th className="px-4 py-2 font-medium">Product</th>
                    <th className="px-3 py-2 font-medium">Latest</th>
                    <th className="px-3 py-2 font-medium">Stock</th>
                    <th className="px-3 py-2 font-medium">Cadence</th>
                    <th className="px-3 py-2 font-medium">Last scraped</th>
                    <th className="px-4 py-2 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.trackers.map((tracker) => (
                    <tr
                      key={tracker.id}
                      className="border-b border-line last:border-0"
                    >
                      <td className="px-4 py-2.5">
                        <Link
                          to={`/product/${tracker.productId}`}
                          className="font-medium text-ink hover:underline"
                        >
                          {tracker.product?.name ?? `Product #${tracker.productId}`}
                        </Link>
                        {tracker.product?.brand ? (
                          <div className="text-[11px] text-ink-faint">
                            {tracker.product.brand}
                          </div>
                        ) : null}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2.5 font-medium text-ink">
                        {formatCurrency(
                          tracker.latest?.price ?? null,
                          tracker.latest?.currency,
                        )}
                      </td>
                      <td className="px-3 py-2.5">
                        <StockBadge
                          inStock={tracker.latest?.inStock}
                          label={tracker.latest?.stockLabel}
                        />
                      </td>
                      <td className="whitespace-nowrap px-3 py-2.5 text-ink-secondary">
                        {formatRefresh(tracker.refreshMinutes)}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2.5 text-ink-secondary">
                        {formatRelative(
                          tracker.lastScrapedAt ?? tracker.latest?.capturedAt,
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            size="sm"
                            variant="ghost"
                            loading={busy === `refresh-${tracker.id}`}
                            onClick={() => handleRefresh(tracker)}
                          >
                            Refresh
                          </Button>
                          <Link to={`/tracker/${tracker.id}`}>
                            <Button size="sm" variant="ghost">
                              Settings
                            </Button>
                          </Link>
                          {confirmId === tracker.id ? (
                            <Button
                              size="sm"
                              variant="danger"
                              loading={busy === `untrack-${tracker.id}`}
                              onClick={() => handleUntrack(tracker)}
                            >
                              Confirm
                            </Button>
                          ) : (
                            <Button
                              size="sm"
                              variant="danger"
                              onClick={() => setConfirmId(tracker.id)}
                            >
                              Untrack
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel title="Recent scrape log" bodyClassName="p-3">
          {loading && !data ? (
            <SkeletonRows rows={4} />
          ) : (
            <LogTable logs={data?.recentLogs ?? []} />
          )}
        </Panel>

        <Panel
          title="Recent notifications"
          action={
            <Link
              to="/notifications"
              className="text-[12px] text-ink-secondary hover:text-ink hover:underline"
            >
              View all
            </Link>
          }
          bodyClassName="p-0"
        >
          {loading && !data ? (
            <div className="p-4">
              <SkeletonRows rows={3} />
            </div>
          ) : !data || data.notifications.length === 0 ? (
            <div className="p-4">
              <EmptyState
                title="No alerts yet"
                description="Price drop and back-in-stock alerts will appear here."
              />
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {data.notifications.slice(0, 6).map((notification) => (
                <li key={notification.id} className="px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    <NotificationTypeBadge type={notification.type} />
                    <NotificationStatusBadge status={notification.status} />
                  </div>
                  <Link
                    to={`/product/${notification.productId}`}
                    className="mt-1 block text-[12px] text-ink hover:underline"
                  >
                    {notification.title ||
                      notification.message ||
                      `Product #${notification.productId}`}
                  </Link>
                  <SectionLabel className="mt-0.5">
                    {formatRelative(notification.sentAt ?? notification.createdAt)}
                  </SectionLabel>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
