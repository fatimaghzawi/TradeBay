import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

export type PaginationProps = {
  page: number;
  pageCount: number;
  onPageChange: (page: number) => void;
  className?: string;
};

export function Pagination({
  page,
  pageCount,
  onPageChange,
  className,
}: PaginationProps) {
  const safeCount = Math.max(1, pageCount);
  const current = Math.min(Math.max(1, page), safeCount);

  return (
    <nav
      aria-label="Pagination"
      className={cn("flex items-center gap-2", className)}
    >
      <Button
        variant="outline"
        size="sm"
        disabled={current <= 1}
        onClick={() => onPageChange(current - 1)}
      >
        Previous
      </Button>
      <span className="text-sm text-muted-foreground">
        Page {current} of {safeCount}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={current >= safeCount}
        onClick={() => onPageChange(current + 1)}
      >
        Next
      </Button>
    </nav>
  );
}
