import { Link } from "react-router-dom";
import { Button, EmptyState, PageHeader } from "../components/ui";

export function NotFoundPage() {
  return (
    <div>
      <PageHeader title="Not found" subtitle="That page doesn't exist." />
      <EmptyState
        title="404"
        description="The page you're looking for may have been moved or removed."
        action={
          <Link to="/">
            <Button variant="primary" size="sm">
              Back to dashboard
            </Button>
          </Link>
        }
      />
    </div>
  );
}
