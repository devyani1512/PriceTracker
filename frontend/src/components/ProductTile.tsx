import { Link } from "react-router-dom";
import type { ProductCard } from "../api";
import { Badge, Button } from "./ui";

export function ProductTile({
  product,
  tracked,
  tracking,
  onTrack,
}: {
  product: ProductCard;
  tracked?: boolean;
  tracking?: boolean;
  onTrack?: (product: ProductCard) => void;
}) {
  return (
    <div className="flex flex-col justify-between rounded border border-line bg-white p-4 transition-colors hover:border-ink-faint/40">
      <div className="min-w-0">
        <div className="flex items-start justify-between gap-2">
          <Link
            to={`/product/${product.id}`}
            className="text-[13px] font-medium leading-snug text-ink hover:underline"
          >
            {product.name}
          </Link>
          {product.structureChanged ? (
            <Badge tone="warning" className="shrink-0">
              structure
            </Badge>
          ) : null}
        </div>
        <div className="mt-0.5 text-[11px] text-ink-faint">
          {[product.brand, product.category].filter(Boolean).join(" · ") ||
            "Uncategorised"}
        </div>
        {product.description ? (
          <p className="mt-2 line-clamp-2 text-[12px] text-ink-secondary">
            {product.description}
          </p>
        ) : null}
        {product.sku ? (
          <div className="mt-2 text-[11px] text-ink-faint">SKU {product.sku}</div>
        ) : null}
      </div>
      <div className="mt-4 flex items-center justify-between gap-2">
        <Link
          to={`/product/${product.id}`}
          className="text-[12px] text-ink-secondary hover:text-ink hover:underline"
        >
          View details
        </Link>
        {onTrack ? (
          tracked ? (
            <Badge tone="success">Tracking</Badge>
          ) : (
            <Button
              size="sm"
              variant="secondary"
              loading={tracking}
              onClick={() => onTrack(product)}
            >
              Track
            </Button>
          )
        ) : null}
      </div>
    </div>
  );
}
