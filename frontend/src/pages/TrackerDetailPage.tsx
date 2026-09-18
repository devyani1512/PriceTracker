import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { trackerApi } from "../api";
import type { UpdateTrackerInput } from "../api";
import { useAsync } from "../hooks/useAsync";
import { errorMessage } from "../lib/utils";
import { formatCurrency, formatRelative } from "../lib/format";
import { LogTable } from "../components/LogTable";
import { PriceChart } from "../components/PriceChart";
import { SnapshotTable } from "../components/SnapshotTable";
import {
  Banner,
  Button,
  EmptyState,
  Field,
  InlineError,
  Input,
  PageHeader,
  Panel,
  SkeletonRows,
  Toggle,
} from "../components/ui";

interface FormState {
  refreshMinutes: number;
  active: boolean;
  alertOnPriceDrop: boolean;
  priceDropThresholdPct: number;
  alertOnBackInStock: boolean;
}

export function TrackerDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();

  const tracker = useAsync(() => trackerApi.get(id), [id]);
  const [form, setForm] = useState<FormState | null>(null);
  const [days, setDays] = useState(30);
  const history = useAsync(() => trackerApi.history(id, days), [id, days]);
  const logs = useAsync(() => trackerApi.logs(id, 20, 1), [id]);

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!tracker.data) return;
    setForm({
      refreshMinutes: tracker.data.refreshMinutes,
      active: tracker.data.active,
      alertOnPriceDrop: tracker.data.alertOnPriceDrop,
      priceDropThresholdPct: tracker.data.priceDropThresholdPct ?? 10,
      alertOnBackInStock: tracker.data.alertOnBackInStock,
    });
  }, [tracker.data]);

  async function handleSave() {
    if (!form) return;
    if (form.refreshMinutes < 10) {
      setError("Refresh cadence must be at least 10 minutes.");
      return;
    }
    setBusy("save");
    setError(null);
    setNotice(null);
    const body: UpdateTrackerInput = {
      refreshMinutes: form.refreshMinutes,
      active: form.active,
      alertOnPriceDrop: form.alertOnPriceDrop,
      priceDropThresholdPct: form.priceDropThresholdPct,
      alertOnBackInStock: form.alertOnBackInStock,
    };
    try {
      const next = await trackerApi.update(id, body);
      tracker.setData(next);
      setNotice("Settings saved.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleUntrack() {
    setBusy("untrack");
    setError(null);
    try {
      await trackerApi.remove(id);
      navigate("/");
    } catch (err) {
      setError(errorMessage(err));
      setBusy(null);
    }
  }

  if (tracker.loading && !tracker.data) {
    return (
      <div>
        <SkeletonRows rows={2} className="mb-6" />
        <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
          <Panel title="Settings">
            <SkeletonRows rows={5} />
          </Panel>
          <Panel title="Price history">
            <SkeletonRows rows={6} />
          </Panel>
        </div>
      </div>
    );
  }

  if (tracker.error || !tracker.data) {
    return (
      <div>
        <PageHeader
          title="Tracker"
          back={
            <Link to="/" className="text-ink-secondary hover:underline">
              ← Back to dashboard
            </Link>
          }
        />
        <InlineError>{tracker.error ?? "Tracker not found."}</InlineError>
      </div>
    );
  }

  const cadenceChanged =
    form !== null && form.refreshMinutes !== tracker.data.refreshMinutes;

  return (
    <div>
      <PageHeader
        title={tracker.data.product?.name ?? `Tracker ${tracker.data.id}`}
        back={
          <Link to="/" className="text-ink-secondary hover:underline">
            ← Back to dashboard
          </Link>
        }
        subtitle={
          <span>
            {tracker.data.product?.brand ? `${tracker.data.product.brand} · ` : ""}
            {tracker.data.active ? "Active" : "Paused"} · Latest{" "}
            {formatCurrency(
              tracker.data.latest?.price ?? null,
              tracker.data.latest?.currency,
            )}{" "}
            · {formatRelative(tracker.data.lastScrapedAt)}
          </span>
        }
        action={
          <div className="flex items-center gap-2">
            <Link to={`/product/${tracker.data.productId}`}>
              <Button variant="ghost">View product</Button>
            </Link>
            {confirming ? (
              <Button
                variant="danger"
                loading={busy === "untrack"}
                onClick={handleUntrack}
              >
                Confirm untrack
              </Button>
            ) : (
              <Button variant="danger" onClick={() => setConfirming(true)}>
                Untrack
              </Button>
            )}
          </div>
        }
      />

      {error ? <InlineError className="mb-4">{error}</InlineError> : null}
      {notice ? (
        <div className="mb-4 rounded-sm border border-success-bg bg-success-bg px-2.5 py-1.5 text-[12px] text-success-text">
          {notice}
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
        <div className="space-y-6">
          <Panel
            title="Tracker settings"
            action={<span className="text-[11px] text-ink-faint">min cadence 10 min</span>}
          >
            {form ? (
              <div className="space-y-4">
                <Field
                  label="Refresh cadence (minutes)"
                  hint="How often this product is checked."
                >
                  <Input
                    type="number"
                    min={10}
                    value={form.refreshMinutes}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        refreshMinutes: Number(event.target.value),
                      })
                    }
                  />
                </Field>

                {cadenceChanged ? (
                  <Banner tone="warning" title="Changing cadence deletes stored history.">
                    Saved price snapshots for this tracker will be cleared when
                    you save a new cadence.
                  </Banner>
                ) : null}

                <div className="border-t border-line pt-1">
                  <Toggle
                    checked={form.active}
                    onChange={(active) => setForm({ ...form, active })}
                    label="Active"
                    description="Pause to stop scheduled scrapes."
                  />
                  <Toggle
                    checked={form.alertOnPriceDrop}
                    onChange={(alertOnPriceDrop) =>
                      setForm({ ...form, alertOnPriceDrop })
                    }
                    label="Alert on price drop"
                  />
                  {form.alertOnPriceDrop ? (
                    <div className="pb-2 pl-0">
                      <Field label="Price drop threshold (%)">
                        <Input
                          type="number"
                          min={0}
                          max={100}
                          value={form.priceDropThresholdPct}
                          onChange={(event) =>
                            setForm({
                              ...form,
                              priceDropThresholdPct: Number(event.target.value),
                            })
                          }
                        />
                      </Field>
                    </div>
                  ) : null}
                  <Toggle
                    checked={form.alertOnBackInStock}
                    onChange={(alertOnBackInStock) =>
                      setForm({ ...form, alertOnBackInStock })
                    }
                    label="Alert when back in stock"
                  />
                </div>

                <Button
                  variant="primary"
                  className="w-full"
                  loading={busy === "save"}
                  onClick={handleSave}
                >
                  Save settings
                </Button>
              </div>
            ) : (
              <SkeletonRows rows={5} />
            )}
          </Panel>

          <Panel title="Per-tracker scrape log" bodyClassName="p-3">
            {logs.loading && !logs.data ? (
              <SkeletonRows rows={4} />
            ) : (
              <LogTable logs={logs.data?.items ?? []} />
            )}
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel
            title="Price history"
            action={
              <div className="flex items-center gap-1">
                {[7, 30, 90, 365].map((option) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => setDays(option)}
                    className={
                      "rounded-sm px-1.5 py-0.5 text-[11px] " +
                      (days === option
                        ? "bg-hover font-medium text-ink"
                        : "text-ink-faint hover:bg-hover hover:text-ink")
                    }
                  >
                    {option === 365 ? "1y" : `${option}d`}
                  </button>
                ))}
              </div>
            }
          >
            {history.loading && !history.data ? (
              <SkeletonRows rows={6} />
            ) : history.data && history.data.points.length > 0 ? (
              <PriceChart
                points={history.data.points}
                currency={
                  history.data.points.length > 0
                    ? history.data.points[history.data.points.length - 1].currency
                    : null
                }
              />
            ) : (
              <EmptyState
                title="No price history"
                description="Snapshots will appear after the next successful scrape."
              />
            )}
          </Panel>

          {history.data && history.data.stats ? (
            <Panel title="History stats">
              <dl className="grid grid-cols-2 gap-3 text-[12px] sm:grid-cols-3">
                <div>
                  <dt className="text-ink-faint">Count</dt>
                  <dd className="text-ink">{history.data.stats.count}</dd>
                </div>
                <div>
                  <dt className="text-ink-faint">Min</dt>
                  <dd className="text-ink">
                    {formatCurrency(history.data.stats.min)}
                  </dd>
                </div>
                <div>
                  <dt className="text-ink-faint">Max</dt>
                  <dd className="text-ink">
                    {formatCurrency(history.data.stats.max)}
                  </dd>
                </div>
                <div>
                  <dt className="text-ink-faint">Current</dt>
                  <dd className="text-ink">
                    {formatCurrency(history.data.stats.current)}
                  </dd>
                </div>
                <div>
                  <dt className="text-ink-faint">First</dt>
                  <dd className="text-ink">
                    {formatCurrency(history.data.stats.first)}
                  </dd>
                </div>
                <div>
                  <dt className="text-ink-faint">Change</dt>
                  <dd className="text-ink">
                    {history.data.stats.changePct === null
                      ? "—"
                      : `${history.data.stats.changePct.toFixed(1)}%`}
                  </dd>
                </div>
              </dl>
            </Panel>
          ) : null}

          {history.data && history.data.points.length > 0 ? (
            <Panel title="Snapshot history" bodyClassName="p-3">
              <SnapshotTable points={history.data.points} />
            </Panel>
          ) : null}
        </div>
      </div>
    </div>
  );
}
