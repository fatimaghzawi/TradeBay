import type { Product } from "@/lib/api/catalogApi";
import { mediaUrl } from "@/lib/media";

export function productPrimaryImageUrl(
  product: Pick<Product, "images" | "primary_image_url">,
): string {
  const url =
    product.images?.find((img) => img.is_primary)?.url ||
    product.primary_image_url ||
    product.images?.[0]?.url ||
    "";
  return mediaUrl(url);
}

export function AdminProductPhoto({
  url,
  alt = "",
  size = "row",
}: {
  url?: string | null;
  alt?: string;
  size?: "row" | "hero";
}) {
  const src = mediaUrl(url);
  return (
    <div className={`tb-admin-photo tb-admin-photo--${size}`}>
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={alt} />
      ) : (
        <span>No photo</span>
      )}
    </div>
  );
}
