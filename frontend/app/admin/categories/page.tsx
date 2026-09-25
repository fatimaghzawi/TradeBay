"use client";

import { AdminAct } from "@/components/admin/AdminUi";
import { PermissionGate } from "@/components/auth/PermissionGate";
import { IdentityPageShell } from "@/components/identity/IdentityPageShell";
import { FeedbackBanner } from "@/components/ui/FeedbackBanner";
import { LoadingEntity, BusyText } from "@/components/ui/LoadingState";
import { Modal } from "@/components/ui/Modal";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { FieldError } from "@/components/ui/FormField";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { catalogApi, type Category } from "@/lib/api/catalogApi";
import { mediaUrl } from "@/lib/media";
import { validateUpload } from "@/lib/validation/common";
import { categoryCreateSchema } from "@/lib/validation/forms";
import { useLiveFields } from "@/lib/validation/live";
import { useCallback, useEffect, useMemo, useState } from "react";

function CategoriesInner() {
  const { success, error: toastError } = useToast();
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [parentId, setParentId] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);
  const live = useLiveFields(categoryCreateSchema, {
    name,
    slug,
    description,
  });

  const reload = useCallback(() => {
    setLoading(true);
    void catalogApi
      .listCategories({ page_size: 100 })
      .then((result) => {
        setCategories(result.data);
        setError(null);
      })
      .catch((err) => {
        setCategories([]);
        setError(
          err instanceof ApiError ? err.message : "Couldn't load categories.",
        );
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    if (!imageFile) {
      setImagePreview(null);
      return;
    }
    const url = URL.createObjectURL(imageFile);
    setImagePreview(url);
    return () => URL.revokeObjectURL(url);
  }, [imageFile]);

  const byId = useMemo(() => {
    const map = new Map<string, Category>();
    for (const c of categories) map.set(c.id, c);
    return map;
  }, [categories]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return categories;
    return categories.filter((c) =>
      [c.name, c.slug, c.description ?? ""].join(" ").toLowerCase().includes(q),
    );
  }, [categories, query]);

  const roots = filtered.filter((c) => !c.parent_category_id);
  const childrenOf = (id: string) =>
    filtered.filter((c) => c.parent_category_id === id);
  const activeCount = categories.filter((c) => c.is_active).length;

  function resetCreateForm() {
    setName("");
    setSlug("");
    setDescription("");
    setParentId("");
    setImageFile(null);
    setImagePreview(null);
    setImageError(null);
    live.reset();
  }

  function submitCreate() {
    if (!live.finish()) return;
    if (imageFile) {
      const message = validateUpload(imageFile, { kinds: "image", label: "Image" });
      if (message) {
        setImageError(message);
        return;
      }
    }
    setPending(true);
    void catalogApi
      .createCategory({
        name: name.trim(),
        slug: slug.trim() || undefined,
        description: description.trim() || undefined,
        parent_category_id: parentId || null,
      })
      .then(async (created) => {
        if (imageFile) {
          try {
            await catalogApi.uploadCategoryImage(created.id, imageFile);
          } catch (err) {
            toastError(
              "Category created",
              err instanceof ApiError
                ? `Saved without image: ${err.message}`
                : "Saved, but image upload failed.",
            );
            setCreateOpen(false);
            resetCreateForm();
            reload();
            return;
          }
        }
        success("Category created", name.trim());
        setCreateOpen(false);
        resetCreateForm();
        reload();
      })
      .catch((err) => {
        toastError(
          "Create failed",
          err instanceof ApiError ? err.message : "Could not create category.",
        );
      })
      .finally(() => setPending(false));
  }

  function renderNode(cat: Category, depth: number) {
    const kids = childrenOf(cat.id);
    const src = mediaUrl(cat.image_url);
    return (
      <li key={cat.id}>
        <div
          className="tb-roles-row"
          style={{ paddingLeft: `${12 + depth * 18}px` }}
        >
          <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-xl border border-border bg-muted">
            {src ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={src} alt="" className="h-full w-full object-cover" />
            ) : (
              <span className="flex h-full w-full items-center justify-center text-sm font-bold text-muted-foreground">
                {cat.name.slice(0, 1).toUpperCase()}
              </span>
            )}
          </div>
          <div className="tb-roles-row-main min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="tb-roles-row-name">{cat.name}</p>
              <span
                className="tb-roles-badge"
                data-kind={cat.parent_category_id ? "custom" : "system"}
              >
                {cat.parent_category_id ? "Child" : "Root"}
              </span>
            </div>
            <p className="tb-roles-row-desc">
              /{cat.slug}
              {cat.parent_category_id
                ? ` · under ${byId.get(cat.parent_category_id)?.name ?? "—"}`
                : " · top level"}
            </p>
          </div>
          <StatusBadge status={cat.is_active ? "active" : "inactive"} />
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="text-sm font-bold text-accent hover:underline"
              onClick={() => {
                void catalogApi
                  .updateCategory(cat.id, { is_active: !cat.is_active })
                  .then(() => {
                    success(
                      cat.is_active ? "Deactivated" : "Activated",
                      cat.name,
                    );
                    reload();
                  })
                  .catch((err) =>
                    toastError(
                      "Update failed",
                      err instanceof ApiError
                        ? err.message
                        : "Could not update.",
                    ),
                  );
              }}
            >
              {cat.is_active ? "Deactivate" : "Activate"}
            </button>
          </div>
        </div>
        {kids.length > 0 ? (
          <ul className="tb-roles-list !mt-0 !gap-0">
            {kids.map((child) => renderNode(child, depth + 1))}
          </ul>
        ) : null}
      </li>
    );
  }

  return (
    <IdentityPageShell
      crumb="Platform / Categories"
      title="Categories"
      mark="Platform"
      action={
        <AdminAct tone="go" arrow onClick={() => setCreateOpen(true)}>
          New category
        </AdminAct>
      }
      banner={{
        icon: "☰",
        title: "Marketplace taxonomy",
        body: "Create categories with an image so shoppers see your artwork across TradeBay.",
      }}
      stats={[
        {
          icon: "☰",
          tone: "teal",
          value: categories.length,
          label: "Total",
        },
        {
          icon: "✓",
          tone: "green",
          value: activeCount,
          label: "Active",
        },
      ]}
      search={query}
      searchPlaceholder="Search categories…"
      onSearchChange={setQuery}
      quote="“A clear taxonomy makes every listing findable.”"
    >
      {error ? (
        <div className="mt-2">
          <FeedbackBanner
            tone="error"
            title="Couldn't load"
            onDismiss={() => setError(null)}
          >
            {error}
          </FeedbackBanner>
        </div>
      ) : null}

      {loading ? (
        <LoadingEntity entity="categories" className="py-12" />
      ) : filtered.length === 0 ? (
        <div className="tb-empty">
          <h3>No categories yet</h3>
          <p>Create the first root category to start the product taxonomy.</p>
          <AdminAct
            tone="go"
            arrow
            className="mt-4"
            onClick={() => setCreateOpen(true)}
          >
            New category
          </AdminAct>
        </div>
      ) : (
        <ul className="tb-roles-list">
          {roots.map((root) => renderNode(root, 0))}
        </ul>
      )}

      <button
        type="button"
        className="tb-roles-create-card w-full text-left"
        onClick={() => setCreateOpen(true)}
      >
        <span className="tb-roles-create-plus" aria-hidden>
          +
        </span>
        <span>
          <strong>Create a Category</strong>
          <em>Name it, optionally nest it, and attach an image.</em>
        </span>
        <span className="tb-roles-create-go" aria-hidden>
          →
        </span>
      </button>

      <Modal
        open={createOpen}
        onClose={() => {
          if (pending) return;
          setCreateOpen(false);
          resetCreateForm();
        }}
        title="Create category"
        asideTitle="Taxonomy"
        asideBody="Add name and an optional image — the picture shows in the marketplace and landing."
        footer={
          <>
            <button
              type="button"
              className="tb-btn tb-btn--outline"
              disabled={pending}
              onClick={() => {
                setCreateOpen(false);
                resetCreateForm();
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              className="tb-btn tb-btn--primary"
              disabled={pending || !name.trim()}
              onClick={submitCreate}
             aria-busy={pending || undefined}>
              <BusyText busy={pending}>{pending ? "Creating…" : "Create →"}</BusyText>
            </button>
          </>
        }
      >
        <label className="tb-split-field" data-state={live.errors.name ? "error" : undefined}>
          <span>Name</span>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={() => live.touch("name")}
            placeholder="Electronics"
          />
          <FieldError error={live.errors.name} />
        </label>
        <label className="tb-split-field mt-3" data-state={live.errors.slug ? "error" : undefined}>
          <span>Slug (optional)</span>
          <input
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            onBlur={() => live.touch("slug")}
            placeholder="electronics"
          />
          <FieldError error={live.errors.slug} />
        </label>
        <label className="tb-split-field mt-3">
          <span>Parent</span>
          <select
            value={parentId}
            onChange={(e) => setParentId(e.target.value)}
          >
            <option value="">None (top level)</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="tb-split-field mt-3">
          <span>Description</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onBlur={() => live.touch("description")}
            rows={3}
          />
          <FieldError error={live.errors.description} />
        </label>
        <div className="tb-split-field mt-3">
          <span>Image (optional)</span>
          <div className="mt-2 flex items-center gap-3">
            <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-xl border border-border bg-muted">
              {imagePreview ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={imagePreview}
                  alt=""
                  className="h-full w-full object-cover"
                />
              ) : (
                <span className="flex h-full w-full items-center justify-center text-xs font-semibold text-muted-foreground">
                  —
                </span>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <label className="inline-flex cursor-pointer items-center rounded-full border border-input bg-card px-3 py-1.5 text-sm font-semibold text-heading">
                {imageFile ? "Change image" : "Choose image"}
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  className="sr-only"
                  onChange={(e) => {
                    const file = e.target.files?.[0] ?? null;
                    if (file) {
                      const message = validateUpload(file, {
                        kinds: "image",
                        label: "Image",
                      });
                      if (message) {
                        setImageError(message);
                        setImageFile(null);
                        e.target.value = "";
                        return;
                      }
                    }
                    setImageError(null);
                    setImageFile(file);
                    e.target.value = "";
                  }}
                />
              </label>
              {imageFile ? (
                <button
                  type="button"
                  className="ml-2 text-sm font-semibold text-muted-foreground hover:underline"
                  onClick={() => setImageFile(null)}
                >
                  Clear
                </button>
              ) : null}
              <p className="mt-1 text-xs text-muted-foreground">
                JPEG, PNG, WebP, or GIF
              </p>
              <FieldError error={imageError} />
            </div>
          </div>
        </div>
      </Modal>
    </IdentityPageShell>
  );
}

export default function AdminCategoriesPage() {
  return (
    <PermissionGate
      permission={["categories.manage", "categories.read"]}
      fallbackTitle="Categories locked"
      fallbackDescription="Platform staff access is required to edit the product taxonomy."
    >
      <CategoriesInner />
    </PermissionGate>
  );
}
