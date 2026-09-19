import { Link } from "react-router-dom";
import type { ScrapeLog } from "../api";
import {
  formatCurrency,
  formatDateTime,
  formatDuration,
  formatRelative,
} from "../lib/format";
import { EmptyState, OutcomeBadge, StockBadge } from "./ui";

export function LogTable({ logs }: { logs: ScrapeLog[] }) {
  if (!logs || logs.length === 0) {
    return (
      <EmptyState
        title="No scrape activity"
        description="Scrape attempts and their outcomes will show up here."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[12px]">
        <thead>
          <tr className="border-b border-line text-left text-[11px] uppercase tracking-wide text-ink-faint">
            <th className="py-2 pr-3 font-medium">Product</th>
            <th className="py-2 pr-3 font-medium">When</th>
            <th className="py-2 pr-3 font-medium">Outcome</th>
            <th className="py-2 pr-3 font-medium">Try</th>
            <th className="py-2 pr-3 font-medium">Duration</th>
            <th className="py-2 pr-3 font-medium">Price</th>
            <th className="py-2 pr-3 font-medium">Stock</th>
            <th className="py-2 font-medium">Message</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id} className="border-b border-line last:border-0">
              <td className="max-w-[180px] py-2 pr-3">
                <Link
                  to={`/product/${log.productId}`}
                  className="block truncate text-ink-secondary hover:text-ink hover:underline"
                  title={log.productName ?? `#${log.productId}`}
                >
                  {log.productName ?? `#${log.productId}`}
                </Link>
              </td>
              <td
                className="whitespace-nowrap py-2 pr-3 text-ink-secondary"
                title={formatDateTime(log.createdAt)}
              >
                {formatRelative(log.createdAt)}
              </td>
              <td className="whitespace-nowrap py-2 pr-3">
                <OutcomeBadge outcome={log.outcome} />
              </td>
              <td className="py-2 pr-3 text-ink-faint">{log.attempt}</td>
              <td className="whitespace-nowrap py-2 pr-3 text-ink-faint">
                {formatDuration(log.durationMs)}
              </td>
              <td className="whitespace-nowrap py-2 pr-3 text-ink-secondary">
                {log.price !== null ? formatCurrency(log.price) : "—"}
              </td>
              <td className="whitespace-nowrap py-2 pr-3">
                {log.inStock === null || log.inStock === undefined ? (
                  <span className="text-ink-faint">—</span>
                ) : (
                  <StockBadge inStock={log.inStock} />
                )}
              </td>
              <td className="max-w-[320px] py-2 text-ink-secondary">
                <span className="line-clamp-2">
                  {log.message || log.errorKind || "—"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
