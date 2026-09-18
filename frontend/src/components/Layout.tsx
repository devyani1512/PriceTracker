import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { cn } from "../lib/utils";
import { Button } from "./ui";

function Icon({ path }: { path: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      className="h-3.5 w-3.5 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  );
}

const NAV = [
  { to: "/", label: "Dashboard", end: true, icon: "M2 7.5 8 2l6 5.5M3.5 6.5V14h9V6.5" },
  { to: "/browse", label: "Browse", icon: "M7 12.5a5.5 5.5 0 1 0 0-11 5.5 5.5 0 0 0 0 11ZM14 14l-3.2-3.2" },
  { to: "/notifications", label: "Notifications", icon: "M8 2a3.5 3.5 0 0 0-3.5 3.5c0 3-1.5 4-1.5 4h10s-1.5-1-1.5-4A3.5 3.5 0 0 0 8 2ZM6.5 12a1.5 1.5 0 0 0 3 0" },
  { to: "/settings", label: "Settings", icon: "M8 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM13 8c0-.4 0-.8-.1-1.2l1.3-1-1.3-2.2-1.5.6a5 5 0 0 0-2-1.2L9.2 1.5H6.8L6.6 3a5 5 0 0 0-2 1.2l-1.5-.6L1.8 5.8l1.3 1A6 6 0 0 0 3 8c0 .4 0 .8.1 1.2l-1.3 1 1.3 2.2 1.5-.6a5 5 0 0 0 2 1.2l.2 1.5h2.4l.2-1.5a5 5 0 0 0 2-1.2l1.5.6 1.3-2.2-1.3-1c.1-.4.1-.8.1-1.2Z" },
];

function navClass(active: boolean): string {
  return cn(
    "flex items-center gap-2 rounded px-2 py-1.5 text-[13px] transition-colors",
    active
      ? "bg-hover font-medium text-ink"
      : "text-ink-secondary hover:bg-hover hover:text-ink",
  );
}

function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col justify-between px-3 py-5 md:flex">
      <div>
        <div className="px-2 pb-4">
          <div className="text-[13px] font-semibold text-ink">Price Tracker</div>
          <div className="text-[11px] text-ink-faint">Catalog &amp; alerts</div>
        </div>
        <nav className="space-y-0.5">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => navClass(isActive)}
            >
              <Icon path={item.icon} />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="border-t border-line px-2 pt-3">
        <div className="truncate text-[12px] text-ink-secondary">
          {user?.displayName || user?.email}
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="mt-1 -ml-2"
          onClick={() => {
            logout();
            navigate("/login");
          }}
        >
          Log out
        </Button>
      </div>
    </aside>
  );
}

function MobileNav() {
  return (
    <div className="sticky top-0 z-10 border-b border-line bg-white/95 backdrop-blur md:hidden">
      <div className="flex items-center gap-1 overflow-x-auto px-3 py-2">
        <span className="mr-2 shrink-0 text-[13px] font-semibold text-ink">
          Price Tracker
        </span>
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cn(
                "shrink-0 rounded px-2 py-1 text-[12px]",
                isActive
                  ? "bg-hover font-medium text-ink"
                  : "text-ink-secondary hover:bg-hover",
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
      </div>
    </div>
  );
}

export function AppLayout() {
  return (
    <div className="min-h-screen bg-white text-ink">
      <MobileNav />
      <div className="mx-auto flex w-full max-w-[1200px] items-start">
        <Sidebar />
        <main className="min-h-screen w-full min-w-0 flex-1 border-line md:border-l">
          <div className="mx-auto w-full max-w-content px-5 py-7 md:px-8 md:py-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
