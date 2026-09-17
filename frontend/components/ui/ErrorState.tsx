import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";

export type ErrorStateProps = {
  title?: string;
  message?: string;
  onRetry?: () => void;
};

export function ErrorState({
  title = "Something went wrong",
  message = "We could not load this section. Try again in a moment.",
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="space-y-4">
      <Alert variant="error" title={title}>
        {message}
      </Alert>
      {onRetry ? (
        <Button variant="outline" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
