import { redirect } from "next/navigation";
import { ROUTES } from "@/lib/constants";

export default async function CatalogProductRedirectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(ROUTES.inventoryProduct(id));
}
