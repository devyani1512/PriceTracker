import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { errorMessage } from "../lib/utils";
import { Button, Field, InlineError, Input, PageLoader } from "../components/ui";

type Mode = "login" | "register";

export function LoginPage() {
  const { user, loading, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as { from?: string } | null;
  const from = state?.from && state.from !== "/login" ? state.from : "/";

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="mx-auto max-w-content px-8">
        <PageLoader />
      </div>
    );
  }

  if (user) return <Navigate to={from} replace />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") {
        await login(email.trim(), password);
      } else {
        await register(email.trim(), password, displayName.trim() || undefined);
      }
      navigate(from, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-4">
      <div className="w-full max-w-[360px]">
        <div className="mb-6 text-center">
          <div className="text-[15px] font-semibold text-ink">Price Tracker</div>
          <div className="mt-0.5 text-[12px] text-ink-faint">
            {mode === "login"
              ? "Sign in to your account"
              : "Create a new account"}
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded border border-line bg-white p-5"
        >
          <div className="space-y-3">
            {mode === "register" ? (
              <Field label="Display name" hint="Optional">
                <Input
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="Ada Lovelace"
                  autoComplete="name"
                />
              </Field>
            ) : null}
            <Field label="Email">
              <Input
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
              />
            </Field>
            <Field label="Password">
              <Input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••"
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
              />
            </Field>
          </div>

          {error ? <InlineError className="mt-3">{error}</InlineError> : null}

          <Button
            type="submit"
            variant="primary"
            className="mt-4 w-full"
            loading={busy}
          >
            {mode === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>

        <div className="mt-3 text-center text-[12px] text-ink-secondary">
          {mode === "login" ? (
            <>
              New here?{" "}
              <button
                type="button"
                className="text-ink underline underline-offset-2"
                onClick={() => {
                  setMode("register");
                  setError(null);
                }}
              >
                Create an account
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button
                type="button"
                className="text-ink underline underline-offset-2"
                onClick={() => {
                  setMode("login");
                  setError(null);
                }}
              >
                Sign in
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
