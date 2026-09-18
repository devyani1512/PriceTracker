import { useNavigate } from "react-router-dom";
import { API_URL } from "../api";
import { useAuth } from "../context/AuthContext";
import { formatDateTime } from "../lib/format";
import {
  Button,
  PageHeader,
  Panel,
  SectionLabel,
} from "../components/ui";

export function SettingsPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Account details and environment information."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Account">
          <dl className="space-y-3 text-[13px]">
            <div className="flex justify-between gap-4">
              <dt className="text-ink-faint">Display name</dt>
              <dd className="text-ink">{user?.displayName || "—"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-faint">Email</dt>
              <dd className="text-ink">{user?.email ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-faint">User ID</dt>
              <dd className="text-ink">{user?.id ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-ink-faint">Member since</dt>
              <dd className="text-ink">{formatDateTime(user?.createdAt)}</dd>
            </div>
          </dl>
        </Panel>

        <Panel title="Environment">
          <SectionLabel>Backend API URL</SectionLabel>
          <div className="mt-1.5 rounded-sm border border-line bg-panel px-2.5 py-2 font-mono text-[12px] text-code">
            {API_URL}
          </div>
          <p className="mt-2 text-[11px] text-ink-faint">
            Configured via <span className="font-mono">VITE_API_URL</span> at
            build time. Session tokens are stored in{" "}
            <span className="font-mono">localStorage["pt_token"]</span>.
          </p>
        </Panel>

        <Panel title="Session" className="lg:col-span-2">
          <div className="flex items-center justify-between gap-4">
            <p className="text-[12px] text-ink-secondary">
              Signing out clears the stored token from this browser.
            </p>
            <Button
              variant="danger"
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              Log out
            </Button>
          </div>
        </Panel>
      </div>
    </div>
  );
}
