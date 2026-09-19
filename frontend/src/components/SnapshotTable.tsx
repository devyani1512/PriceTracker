import type { Snapshot } from "../api";
import { formatCurrency, formatDateTime, formatNumber, formatPercent } from "../lib/format";
import { EmptyState, StockBadge } from "./ui";

export function SnapshotTable({
  points,
  limit,
}: {
  points: Snapshot[];
  limit?: number;
}) {
  if (!points || points.length === 0) {
    return (
      <EmptyState
        title="No snapshots yet"
        description="Captured prices will appear here once a scrape has run."
      />
    );
  }

  const rows = [...points]
    .sort(
      (a, b) =>
        new Date(b.slotAt || b.capturedAt).getTime() -
        new Date(a.slotAt || a.capturedAt).getTime(),
    )
    .slice(0, limit ?? points.length);

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[12px]">
        <thead>
          <tr className="border-b border-line text-left text-[11px] uppercase tracking-wide text-ink-faint">
            <th className="py-2 pr-3 font-medium">Slot</th>
            <th className="py-2 pr-3 font-medium">Price</th>
            <th className="py-2 pr-3 font-medium">Was</th>
            <th className="py-2 pr-3 font-medium">Disc.</th>
            <th className="py-2 pr-3 font-medium">Stock</th>
            <th className="py-2 font-medium">Trigger</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((point) => (
            <tr key={point.id} className="border-b border-line last:border-0">
              <td className="whitespace-nowrap py-2 pr-3 text-ink-secondary">
                {formatDateTime(point.slotAt || point.capturedAt)}
              </td>
              <td className="whitespace-nowrap py-2 pr-3 font-medium text-ink">
                {formatCurrency(point.price, point.currency)}
              </td>
              <td className="whitespace-nowrap py-2 pr-3 text-ink-faint">
                {point.wasPrice !== null
                  ? formatCurrency(point.wasPrice, point.currency)
                  : "—"}
              </td>
              <td className="whitespace-nowrap py-2 pr-3 text-ink-secondary">
                {point.discountPct !== null
                  ? formatPercent(-Math.abs(point.discountPct), 0)
                  : "—"}
              </td>
              <td className="whitespace-nowrap py-2 pr-3">
                <StockBadge
                  inStock={point.inStock}
                  label={point.stockLabel}
                  count={point.stockCount}
                />
              </td>
              <td className="whitespace-nowrap py-2 text-ink-faint">
                {point.trigger || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {limit && points.length > limit ? (
        <p className="pt-2 text-[11px] text-ink-faint">
          Showing the latest {formatNumber(limit, 0)} of {points.length} snapshots.
        </p>
      ) : null}
    </div>
  );
}
