import { Link } from "react-router-dom";
import { notificationApi } from "../api";
import { useAsync } from "../hooks/useAsync";
import { formatDateTime, formatRelative, formatPercent } from "../lib/format";
import {
  Button,
  EmptyState,
  InlineError,
  NotificationStatusBadge,
  NotificationTypeBadge,
  PageHeader,
  Panel,
  SkeletonRows,
} from "../components/ui";

export function NotificationsPage() {
  const { data, loading, error, reload } = useAsync(
    () => notificationApi.list(),
    [],
  );

  return (
    <div>
      <PageHeader
        title="Notifications"
        subtitle="Price drop and back-in-stock alerts across your trackers."
        action={
          <Button variant="secondary" loading={loading} onClick={reload}>
            Refresh
          </Button>
        }
      />

      {error ? <InlineError className="mb-4">{error}</InlineError> : null}

      <Panel bodyClassName="p-0">
        {loading && !data ? (
          <div className="p-4">
            <SkeletonRows rows={5} />
          </div>
        ) : !data || data.length === 0 ? (
          <div className="p-4">
            <EmptyState
              title="No notifications yet"
              description="When a tracked product drops in price or comes back in stock, alerts will show up here."
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
          <ul className="divide-y divide-line">
            {data.map((notification) => (
              <li key={notification.id} className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-1.5">
                  <NotificationTypeBadge type={notification.type} />
                  <NotificationStatusBadge status={notification.status} />
                  {notification.thresholdPct !== null ? (
                    <span className="text-[11px] text-ink-faint">
                      threshold {formatPercent(notification.thresholdPct, 0)}
                    </span>
                  ) : null}
                </div>

                <div className="mt-1.5 text-[13px] text-ink">
                  {notification.title || "Price alert"}
                </div>
                {notification.message ? (
                  <p className="text-[12px] text-ink-secondary">
                    {notification.message}
                  </p>
                ) : null}

                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-faint">
                  <Link
                    to={`/product/${notification.productId}`}
                    className="hover:text-ink hover:underline"
                  >
                    Product #{notification.productId}
                  </Link>
                  <span title={formatDateTime(notification.createdAt)}>
                    created {formatRelative(notification.createdAt)}
                  </span>
                  {notification.sentAt ? (
                    <span>sent {formatRelative(notification.sentAt)}</span>
                  ) : null}
                </div>

                {notification.error ? (
                  <p className="mt-1 text-[11px] text-danger-text">
                    {notification.error}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
