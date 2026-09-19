import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Snapshot } from "../api";
import { formatCurrency, formatDateTime } from "../lib/format";
import { EmptyState } from "./ui";

interface Datum {
  t: number;
  price: number;
  snapshot: Snapshot;
}

function toDatum(snapshot: Snapshot): Datum | null {
  if (snapshot.price === null || snapshot.price === undefined) return null;
  // Plot on the canonical slot, not the capture moment: a 10:00 value fetched at
  // 10:05 still belongs at 10:00, so the series stays evenly spaced.
  const raw = snapshot.slotAt || snapshot.capturedAt;
  const time = new Date(raw).getTime();
  if (Number.isNaN(time)) return null;
  return { t: time, price: snapshot.price, snapshot };
}

function compact(value: number): string {
  if (Math.abs(value) >= 100000) return `${(value / 100000).toFixed(1)}L`;
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return String(value);
}

function PriceTooltip({
  active,
  payload,
  currency,
}: {
  active?: boolean;
  payload?: Array<{ payload: Datum }>;
  currency?: string | null;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const datum = payload[0].payload;
  return (
    <div className="rounded border border-line bg-white px-2.5 py-1.5 text-[12px] shadow-sm">
      <div className="text-ink">{formatCurrency(datum.price, currency)}</div>
      <div className="text-ink-faint">
        {formatDateTime(datum.snapshot.slotAt || datum.snapshot.capturedAt)}
      </div>
    </div>
  );
}

export function PriceChart({
  points,
  currency,
  height = 240,
}: {
  points: Snapshot[];
  currency?: string | null;
  height?: number;
}) {
  const data = points
    .map(toDatum)
    .filter((value): value is Datum => value !== null)
    .sort((a, b) => a.t - b.t);

  if (data.length < 2) {
    return (
      <EmptyState
        title="Not enough price history"
        description="At least two captured prices are needed to draw a chart."
      />
    );
  }

  const resolvedCurrency = currency ?? data[data.length - 1].snapshot.currency;

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
          <CartesianGrid
            vertical={false}
            stroke="#e9e9e7"
            strokeDasharray="0"
          />
          <XAxis
            dataKey="t"
            type="number"
            scale="time"
            domain={["dataMin", "dataMax"]}
            tick={{ fill: "#9b9a97", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#e9e9e7" }}
            tickFormatter={(value: number) =>
              new Date(value).toLocaleDateString("en-IN", {
                day: "2-digit",
                month: "short",
              })
            }
            minTickGap={24}
          />
          <YAxis
            width={48}
            tick={{ fill: "#9b9a97", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value: number) => compact(value)}
            domain={["auto", "auto"]}
          />
          <Tooltip content={<PriceTooltip currency={resolvedCurrency} />} />
          <Line
            type="monotone"
            dataKey="price"
            stroke="#37352f"
            strokeWidth={1.75}
            dot={false}
            activeDot={{ r: 3, fill: "#37352f", stroke: "#ffffff" }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
