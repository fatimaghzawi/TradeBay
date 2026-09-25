import { InventoryBtn, InventoryFoot } from "@/components/catalog/InventoryUi";

export function Pager({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
}) {
  if (total <= pageSize) return null;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <InventoryFoot
      left={
        <span>
          Page {page} of {pages} · {total} total
        </span>
      }
      right={
        <>
          <InventoryBtn tone="ghost" disabled={page <= 1} onClick={() => onPage(page - 1)}>
            Previous
          </InventoryBtn>
          <InventoryBtn tone="ghost" disabled={page >= pages} onClick={() => onPage(page + 1)}>
            Next
          </InventoryBtn>
        </>
      }
    />
  );
}
