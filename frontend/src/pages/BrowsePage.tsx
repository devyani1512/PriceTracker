import { useEffect, useMemo, useState } from "react";
import { productApi, trackerApi } from "../api";
import type { ProductCard } from "../api";
import { useAsync, useDebounced } from "../hooks/useAsync";
import { errorMessage } from "../lib/utils";
import { ProductTile } from "../components/ProductTile";
import {
  Banner,
  EmptyState,
  InlineError,
  Input,
  PageHeader,
  Pagination,
  Skeleton,
} from "../components/ui";

const PAGE_SIZE = 12;

export function BrowsePage() {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const debouncedQuery = useDebounced(query, 350);

  useEffect(() => {
    setPage(1);
  }, [debouncedQuery]);

  const trimmed = debouncedQuery.trim();
  const products = useAsync(
    () =>
      trimmed
        ? productApi.search(trimmed, page, PAGE_SIZE)
        : productApi.list(page, PAGE_SIZE),
    [trimmed, page],
  );

  const catalog = useAsync(() => productApi.catalogStatus(), []);

  const trackers = useAsync(() => trackerApi.list(), []);
  const trackedIds = useMemo(
    () => new Set((trackers.data ?? []).map((tracker) => tracker.productId)),
    [trackers.data],
  );

  const [trackingId, setTrackingId] = useState<number | null>(null);
  const [trackError, setTrackError] = useState<string | null>(null);

  async function handleTrack(product: ProductCard) {
    setTrackingId(product.id);
    setTrackError(null);
    try {
      await trackerApi.add({ productId: product.id, runNow: true });
      trackers.reload();
    } catch (err) {
      setTrackError(errorMessage(err));
    } finally {
      setTrackingId(null);
    }
  }

  const showSkeleton = products.loading && !products.data;

  return (
    <div>
      <PageHeader
        title="Browse products"
        subtitle="Search the catalog and start tracking prices."
      />

      {catalog.data && !catalog.data.complete ? (
        <Banner tone="warning" title="Catalog sync incomplete" >
          Indexed {catalog.data.count} of {catalog.data.expected} products. Some
          products may not appear yet.
        </Banner>
      ) : null}

      <div className="mt-4 flex items-center gap-3">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search products by name…"
          className="max-w-md"
        />
        {trimmed ? (
          <button
            type="button"
            className="text-[12px] text-ink-secondary hover:text-ink hover:underline"
            onClick={() => setQuery("")}
          >
            Clear
          </button>
        ) : null}
      </div>

      {trackError ? (
        <InlineError className="mt-4">{trackError}</InlineError>
      ) : null}
      {products.error ? (
        <InlineError className="mt-4">{products.error}</InlineError>
      ) : null}

      <div className="mt-5">
        {showSkeleton ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <div
                key={index}
                className="rounded border border-line p-4"
              >
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="mt-2 h-3 w-1/2" />
                <Skeleton className="mt-3 h-3 w-full" />
                <Skeleton className="mt-1.5 h-3 w-5/6" />
              </div>
            ))}
          </div>
        ) : !products.data || products.data.items.length === 0 ? (
          <EmptyState
            title={trimmed ? "No products match your search" : "Catalog is empty"}
            description={
              trimmed
                ? "Try a different or shorter search term."
                : "No products are available yet."
            }
          />
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {products.data.items.map((product) => (
                <ProductTile
                  key={product.id}
                  product={product}
                  tracked={trackedIds.has(product.id)}
                  tracking={trackingId === product.id}
                  onTrack={handleTrack}
                />
              ))}
            </div>
            <Pagination
              page={products.data.page}
              pages={products.data.pages}
              total={products.data.total}
              onChange={setPage}
            />
          </>
        )}
      </div>
    </div>
  );
}
