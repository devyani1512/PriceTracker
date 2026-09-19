import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";
import { cn } from "../lib/utils";
import type { NotificationStatus, NotificationType, ScrapeOutcome } from "../api";

/* ------------------------------------------------------------------ Button */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-ink text-white border border-ink hover:bg-code disabled:opacity-40",
  secondary:
    "bg-white text-ink border border-line hover:bg-hover disabled:opacity-40",
  ghost:
    "bg-transparent text-ink-secondary border border-transparent hover:bg-hover hover:text-ink disabled:opacity-40",
  danger:
    "bg-white text-danger-text border border-line hover:bg-danger-bg disabled:opacity-40",
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "h-7 px-2.5 text-[12px]",
  md: "h-8 px-3 text-[13px]",
};

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  className,
  disabled,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cn(
        "inline-flex shrink-0 items-center justify-center gap-1.5 rounded font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ink/20",
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        className,
      )}
    >
      {loading ? <Spinner className="h-3 w-3" /> : null}
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------- Badge */

type BadgeTone = "neutral" | "success" | "warning" | "danger" | "dark";

const BADGE_TONES: Record<BadgeTone, string> = {
  neutral: "bg-panel text-ink-secondary border-line",
  success: "bg-success-bg text-success-text border-success-bg",
  warning: "bg-warning-bg text-warning-text border-warning-bg",
  danger: "bg-danger-bg text-danger-text border-danger-bg",
  dark: "bg-code text-white border-code",
};

export function Badge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: BadgeTone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm border px-1.5 py-0.5 text-[11px] font-medium leading-4",
        BADGE_TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function OutcomeBadge({ outcome }: { outcome: ScrapeOutcome }) {
  const tone: BadgeTone =
    outcome === "success"
      ? "success"
      : outcome === "retried"
        ? "warning"
        : "danger";
  return <Badge tone={tone}>{outcome}</Badge>;
}

export function NotificationStatusBadge({
  status,
}: {
  status: NotificationStatus;
}) {
  const tone: BadgeTone =
    status === "sent" ? "success" : status === "failed" ? "danger" : "warning";
  return <Badge tone={tone}>{status}</Badge>;
}

export function NotificationTypeBadge({ type }: { type: NotificationType }) {
  return (
    <Badge tone="neutral">
      {type === "price_drop" ? "Price drop" : "Back in stock"}
    </Badge>
  );
}

/* ------------------------------------------------------------------- Panel */

export function Panel({
  title,
  action,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={cn("rounded border border-line bg-white", className)}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <h2 className="text-[13px] font-medium text-ink">{title}</h2>
          {action}
        </header>
      )}
      <div className={cn("p-4", bodyClassName)}>{children}</div>
    </section>
  );
}

export function SectionLabel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "text-[11px] uppercase tracking-wide text-ink-faint",
        className,
      )}
    >
      {children}
    </div>
  );
}

/* -------------------------------------------------------------- Skeleton */

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn("animate-pulse rounded-sm bg-hover", className)} />
  );
}

export function SkeletonRows({
  rows = 3,
  className,
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2", className)}>
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton key={index} className="h-4 w-full" />
      ))}
    </div>
  );
}

/* --------------------------------------------------------------- Spinner */

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-block animate-spin rounded-full border-[1.5px] border-current border-t-transparent",
        className ?? "h-4 w-4",
      )}
      aria-hidden="true"
    />
  );
}

export function PageLoader({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-16 text-[13px] text-ink-faint">
      <Spinner className="h-3.5 w-3.5" />
      {label}…
    </div>
  );
}

/* ------------------------------------------------------------ Empty state */

export function EmptyState({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-1 rounded border border-dashed border-line px-6 py-10 text-center",
        className,
      )}
    >
      <p className="text-[13px] font-medium text-ink-secondary">{title}</p>
      {description ? (
        <p className="max-w-sm text-[12px] text-ink-faint">{description}</p>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

/* ---------------------------------------------------------------- Inline */

export function InlineError({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  if (!children) return null;
  return (
    <div
      className={cn(
        "rounded-sm border border-danger-bg bg-danger-bg px-2.5 py-1.5 text-[12px] text-danger-text",
        className,
      )}
    >
      {children}
    </div>
  );
}

type BannerTone = "warning" | "danger" | "info" | "success";

const BANNER_TONES: Record<BannerTone, string> = {
  warning: "bg-warning-bg text-warning-text border-warning-bg",
  danger: "bg-danger-bg text-danger-text border-danger-bg",
  success: "bg-success-bg text-success-text border-success-bg",
  info: "bg-panel text-ink-secondary border-line",
};

export function Banner({
  tone = "warning",
  title,
  children,
  action,
}: {
  tone?: BannerTone;
  title?: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex items-start justify-between gap-3 rounded-sm border px-3 py-2 text-[12px]",
        BANNER_TONES[tone],
      )}
    >
      <div>
        {title ? <p className="font-medium">{title}</p> : null}
        {children ? <div className="mt-0.5 opacity-90">{children}</div> : null}
      </div>
      {action}
    </div>
  );
}

/* --------------------------------------------------------------- Stat card */

export function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
}) {
  return (
    <div className="rounded border border-line bg-white px-4 py-3">
      <SectionLabel>{label}</SectionLabel>
      <div className="mt-1.5 text-[22px] font-semibold leading-none text-ink">
        {value}
      </div>
      {hint ? (
        <div className="mt-1 text-[11px] text-ink-faint">{hint}</div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------ Page header */

export function PageHeader({
  title,
  subtitle,
  action,
  back,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  back?: ReactNode;
}) {
  return (
    <header className="mb-6">
      {back ? <div className="mb-2 text-[12px]">{back}</div> : null}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[20px] font-semibold leading-tight text-ink">
            {title}
          </h1>
          {subtitle ? (
            <div className="mt-1 text-[13px] text-ink-secondary">{subtitle}</div>
          ) : null}
        </div>
        {action ? (
          <div className="flex shrink-0 items-center gap-2">{action}</div>
        ) : null}
      </div>
    </header>
  );
}

/* -------------------------------------------------------------- Form bits */

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-[12px] font-medium text-ink-secondary">
        {label}
      </span>
      {children}
      {hint ? (
        <span className="mt-1 block text-[11px] text-ink-faint">{hint}</span>
      ) : null}
    </label>
  );
}

export function Input({
  className,
  ...rest
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...rest}
      className={cn(
        "h-8 w-full rounded border border-line bg-white px-2.5 text-[13px] text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none focus-visible:ring-2 focus-visible:ring-ink/10",
        className,
      )}
    />
  );
}

export function Select({
  className,
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...rest}
      className={cn(
        "h-8 w-full rounded border border-line bg-white px-2 text-[13px] text-ink focus:border-ink-faint focus:outline-none focus-visible:ring-2 focus-visible:ring-ink/10",
        className,
      )}
    >
      {children}
    </select>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <div>
        <div className="text-[13px] text-ink">{label}</div>
        {description ? (
          <div className="text-[11px] text-ink-faint">{description}</div>
        ) : null}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative mt-0.5 h-4 w-7 shrink-0 rounded-full border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ink/20 disabled:opacity-40",
          checked ? "border-ink bg-ink" : "border-line bg-hover",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-2.5 w-2.5 rounded-full bg-white transition-all",
            checked ? "left-3.5" : "left-0.5",
          )}
        />
      </button>
    </div>
  );
}

/* ------------------------------------------------------------- Pagination */

export function Pagination({
  page,
  pages,
  total,
  onChange,
}: {
  page: number;
  pages: number;
  total?: number;
  onChange: (next: number) => void;
}) {
  if (!pages || pages <= 1) return null;
  return (
    <div className="flex items-center justify-between gap-3 pt-3 text-[12px] text-ink-secondary">
      <button
        type="button"
        className="rounded border border-line px-2 py-1 hover:bg-hover disabled:opacity-40"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        ← Prev
      </button>
      <span className="text-ink-faint">
        Page {page} of {pages}
        {typeof total === "number" ? ` · ${total} items` : ""}
      </span>
      <button
        type="button"
        className="rounded border border-line px-2 py-1 hover:bg-hover disabled:opacity-40"
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
      >
        Next →
      </button>
    </div>
  );
}

/* -------------------------------------------------------------- Stock pill */

export function StockBadge({
  inStock,
  label,
  count,
}: {
  inStock: boolean | null | undefined;
  label?: string | null;
  count?: number | null;
}) {
  const tone: BadgeTone =
    inStock === true ? "success" : inStock === false ? "danger" : "neutral";
  const text =
    label ??
    (inStock === true ? "In stock" : inStock === false ? "Out of stock" : "Unknown");
  return (
    <Badge tone={tone}>
      {text}
      {count !== null && count !== undefined ? ` · ${count}` : ""}
    </Badge>
  );
}
