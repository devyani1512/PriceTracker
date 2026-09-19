import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { notificationApi, productApi, trackerApi } from "../api";
import { useAsync } from "../hooks/useAsync";
import { errorMessage } from "../lib/utils";
import {
  asRecord,
  formatCurrency,
  formatDate,
  formatNumber,
  formatPercent,
  formatRelative,
} from "../lib/format";
import { LogTable } from "../components/LogTable";
import { PriceChart } from "../components/PriceChart";
import { SnapshotTable } from "../components/SnapshotTable";
import {
  Banner,
  Button,
  EmptyState,
  InlineError,
  PageHeader,
  Panel,
  SkeletonRows,
  StockBadge,
} from "../components/ui";

export function ProductDetailPage() {
  const { id = "" } = useParams();
  const numericId = Number(id);

  const product = useAsync(() => productApi.get(id), [id]);
  const trackers = useAsync(() => trackerApi.list(), []);
  const logs = useAsync(() => productApi.logs(id, 20, 1), [id]);

  const tracker = useMemo(
    () => (trackers.data ?? []).find((item) => item.productId === numericId),
    [trackers.data, numericId],
  );

  const [days, setDays] = useState(30);
  const history = useAsync(
    async () => (tracker ? trackerApi.history(tracker.id, days) : null),
    [tracker?.id, days],
  );

  const [polling, setPolling] = useState(false);
  const [subscribed, setSubscribed] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Start polling when the product still has no captured price.
  useEffect(() => {
    if (product.data?.pending && !product.data.latest) {
      setPolling(true);
    }
  }, [product.data?.pending, product.data?.latest]);

  useEffect(() => {
    if (!polling) return;
    const started = Date.now();
    const handle = window.setInterval(async () => {
      if (Date.now() - started > 60_000) {
        setPolling(false);
        return;
      }
      try {
        const next = await productApi.get(id);
        product.setData(next);
        if (next.latest && !next.pending) setPolling(false);
      } catch {
        /* keep polling until timeout */
      }
    }, 3000);
    return () => window.clearInterval(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [polling, id]);

  async function handleRefresh() {
    setBusy("refresh");
    setActionError(null);
    setActionNotice(null);
    try {
      await productApi.refresh(id, false);
      setActionNotice("Refresh queued. Fetching the latest price…");
      setPolling(true);
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleTrack() {
    setBusy("track");
    setActionError(null);
    setActionNotice(null);
    try {
      await trackerApi.add({ productId: numericId, runNow: true });
      trackers.reload();
      setPolling(true);
      setActionNotice("Now tracking this product.");
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleUntrack() {
    if (!tracker) return;
    setBusy("untrack");
    setActionError(null);
    setActionNotice(null);
    try {
      await trackerApi.remove(tracker.id);
      trackers.reload();
      setActionNotice("Stopped tracking this product.");
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleSubscribe() {
    setBusy("subscribe");
    setActionError(null);
    setActionNotice(null);
    try {
      await notificationApi.subscribe({
        productId: numericId,
        trackerId: tracker?.id,
      });
      setSubscribed(true);
      setActionNotice("We'll email you when this product is back in stock.");
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  if (product.loading && !product.data) {
    return (
      <div>
        <SkeletonRows rows={2} className="mb-6" />
        <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
          <Panel title="Price history">
            <SkeletonRows rows={6} />
          </Panel>
          <Panel title="Latest snapshot">
            <SkeletonRows rows={4} />
          </Panel>
        </div>
      </div>
    );
  }

  if (product.error) {
    return (
      <div>
        <PageHeader
          title="Product"
          back={
            <Link to="/browse" className="text-ink-secondary hover:underline">
              ← Back to browse
            </Link>
          }
        />
        <InlineError>{product.error}</InlineError>
        <Button
          variant="secondary"
          className="mt-3"
          onClick={product.reload}
          loading={product.loading}
        >
          Try again
        </Button>
      </div>
    );
  }

  if (!product.data) return null;

  const detail = product.data;
  const latest = detail.latest;
  const outOfStock = latest?.inStock !== true;
  const structureFlag = detail.structureChanged || latest?.structureChanged;

  return (
    <div>
      <PageHeader
        title={detail.name}
        back={
          <Link to="/browse" className="text-ink-secondary hover:underline">
            ← Back to browse
          </Link>
        }
        subtitle={
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {[detail.brand, detail.category].filter(Boolean).join(" · ") || "Uncategorised"}
            {detail.sku ? <span className="text-ink-faint">SKU {detail.sku}</span> : null}
          </span>
        }
        action={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              loading={busy === "refresh"}
              onClick={handleRefresh}
            >
              Refresh
            </Button>
            {tracker ? (
              <Button
                variant="danger"
                loading={busy === "untrack"}
                onClick={handleUntrack}
              >
                Untrack
              </Button>
            ) : (
              <Button
                variant="primary"
                loading={busy === "track"}
                onClick={handleTrack}
              >
                Track
              </Button>
            )}
          </div>
        }
      />

      {structureFlag ? (
        <Banner tone="warning" title="Page structure changed — scraping may be failing.">
          {detail.structureNote ??
            "The product page layout no longer matches the saved scraper."}
        </Banner>
      ) : null}

      {polling ? (
        <Banner tone="info" title="Waiting for the first price…">
          Polling every 3 seconds, up to about a minute.
        </Banner>
      ) : null}

      {actionError ? (
        <InlineError className="mt-4">{actionError}</InlineError>
      ) : null}
      {actionNotice ? (
        <div className="mt-4 rounded-sm border border-success-bg bg-success-bg px-2.5 py-1.5 text-[12px] text-success-text">
          {actionNotice}
        </div>
      ) : null}

      <div className="mt-5 grid gap-6 lg:grid-cols-[1.6fr_1fr]">
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
            {!tracker ? (
              <EmptyState
                title="No tracker yet"
                description="Track this product to collect and chart its price history."
                action={
                  <Button variant="primary" size="sm" onClick={handleTrack}>
                    Track product
                  </Button>
                }
              />
            ) : history.loading && !history.data ? (
              <SkeletonRows rows={6} />
            ) : (
              <PriceChart
                points={history.data?.points ?? []}
                currency={
                  history.data && history.data.points.length > 0
                    ? history.data.points[history.data.points.length - 1].currency
                    : null
                }
              />
            )}
          </Panel>

          {tracker && history.data && history.data.points.length > 0 ? (
            <Panel title="Snapshot history" bodyClassName="p-3">
              <SnapshotTable points={history.data.points} />
            </Panel>
          ) : null}

          <Panel title="Scrape log" bodyClassName="p-3">
            {logs.loading && !logs.data ? (
              <SkeletonRows rows={4} />
            ) : (
              <LogTable logs={logs.data?.items ?? []} />
            )}
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel title="Latest snapshot">
            {latest ? (
              <div>
                <div className="flex items-baseline gap-2">
                  <span className="text-[26px] font-semibold leading-none text-ink">
                    {formatCurrency(latest.price, latest.currency)}
                  </span>
                  {latest.wasPrice !== null &&
                  latest.price !== null &&
                  latest.wasPrice > latest.price ? (
                    <span className="text-[13px] text-ink-faint line-through">
                      {formatCurrency(latest.wasPrice, latest.currency)}
                    </span>
                  ) : null}
                </div>
                {latest.discountPct !== null ? (
                  <div className="mt-1 text-[12px] text-success-text">
                    {formatPercent(-Math.abs(latest.discountPct), 0)} off
                  </div>
                ) : null}
                <div className="mt-3">
                  <StockBadge
                    inStock={latest.inStock}
                    label={latest.stockLabel}
                    count={latest.stockCount}
                  />
                </div>
                <dl className="mt-4 space-y-2 border-t border-line pt-3 text-[12px]">
                  <div className="flex justify-between gap-3">
                    <dt className="text-ink-faint">Captured</dt>
                    <dd className="text-ink-secondary">
                      {formatRelative(latest.capturedAt || latest.slotAt)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-ink-faint">Slot</dt>
                    <dd className="text-ink-secondary">
                      {formatDate(latest.slotAt)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-ink-faint">Trigger</dt>
                    <dd className="text-ink-secondary">{latest.trigger || "—"}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-ink-faint">Snapshots</dt>
                    <dd className="text-ink-secondary">
                      {formatNumber(detail.snapshotCount, 0)}
                    </dd>
                  </div>
                </dl>

                {outOfStock ? (
                  subscribed ? (
                    <div className="mt-4 rounded-sm border border-success-bg bg-success-bg px-2.5 py-1.5 text-center text-[12px] text-success-text">
                      You're on the list
                    </div>
                  ) : (
                    <Button
                      variant="secondary"
                      className="mt-4 w-full"
                      loading={busy === "subscribe"}
                      onClick={handleSubscribe}
                    >
                      Email me when back in stock
                    </Button>
                  )
                ) : null}
              </div>
            ) : (
              <div>
                <EmptyState
                  title={polling ? "Fetching price…" : "No price captured yet"}
                  description="Run a refresh to capture the current price and stock."
                />
              </div>
            )}
          </Panel>

          {tracker ? (
            <Panel title="Tracker">
              <dl className="space-y-2 text-[12px]">
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-faint">Status</dt>
                  <dd className="text-ink-secondary">
                    {tracker.active ? "Active" : "Paused"}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-faint">Cadence</dt>
                  <dd className="text-ink-secondary">
                    every {tracker.refreshMinutes} min
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-ink-faint">Snapshots</dt>
                  <dd className="text-ink-secondary">
                    {formatNumber(tracker.snapshotCount, 0)}
                  </dd>
                </div>
              </dl>
              <Link
                to={`/tracker/${tracker.id}`}
                className="mt-3 inline-block text-[12px] text-ink-secondary hover:text-ink hover:underline"
              >
                Edit tracker settings →
              </Link>
            </Panel>
          ) : null}

          {detail.description ? (
            <Panel title="Description">
              <p className="whitespace-pre-line text-[12px] text-ink-secondary">
                {detail.description}
              </p>
            </Panel>
          ) : null}

          {detail.detailLoaded && asRecord(detail.specs).length > 0 ? (
            <Panel title="Specifications">
              <dl className="space-y-1.5 text-[12px]">
                {asRecord(detail.specs).map(([key, value]) => (
                  <div key={key} className="flex justify-between gap-4">
                    <dt className="text-ink-faint">{key}</dt>
                    <dd className="text-right text-ink-secondary">{value}</dd>
                  </div>
                ))}
              </dl>
            </Panel>
          ) : null}

          {detail.detailLoaded && detail.reviews.length > 0 ? (
            <Panel title={`Reviews (${detail.reviews.length})`}>
              <ul className="space-y-4">
                {detail.reviews.slice(0, 5).map((review) => (
                  <li key={review.id}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[12px] font-medium text-ink">
                        {review.title || "Review"}
                      </span>
                      <span className="text-[11px] text-warning-text">
                        {"★".repeat(Math.round(review.rating))}
                      </span>
                    </div>
                    <div className="text-[11px] text-ink-faint">
                      {review.author}
                      {review.verifiedPurchase ? " · verified" : ""} ·{" "}
                      {formatDate(review.date)}
                    </div>
                    <p className="mt-1 text-[12px] text-ink-secondary">
                      {review.body}
                    </p>
                  </li>
                ))}
              </ul>
            </Panel>
          ) : null}
        </div>
      </div>
    </div>
  );
}
