import { apiClient, type PaginatedResult } from "@/lib/api/client";

export type Category = {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  parent_category_id?: string | null;
  is_active: boolean;
  display_order: number;
  image_url?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type Inventory = {
  id: string;
  product_id: string;
  available_quantity: string;
  reserved_quantity: string;
  updated_at?: string | null;
};

export type ProductPrice = {
  id: string;
  product_id: string;
  min_quantity: number;
  max_quantity: number | null;
  unit_price: string;
  currency: string;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ProductImage = {
  id: string;
  product_id: string;
  url: string;
  alt_text?: string | null;
  is_primary: boolean;
  display_order: number;
  created_at?: string | null;
};

export type Product = {
  id: string;
  supplier_id: string;
  business_account_id: string;
  supplier_name?: string | null;
  supplier_logo_url?: string | null;
  supplier_city?: string | null;
  supplier_governorate?: string | null;
  supplier_verified?: boolean;
  category_id: string;
  sku: string;
  name: string;
  slug: string;
  description?: string | null;
  unit: string;
  origin?: string | null;
  moq: number;
  lead_time_days: number;
  status: string;
  is_featured?: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  inventory?: Inventory | null;
  prices?: ProductPrice[] | null;
  images?: ProductImage[] | null;
  primary_image_url?: string | null;
};

export type InventoryTransaction = {
  id: string;
  inventory_id: string;
  product_id: string;
  transaction_type: string;
  quantity: string;
  reference_type?: string | null;
  reference_id?: string | null;
  previous_available: string;
  previous_reserved: string;
  new_available: string;
  new_reserved: string;
  reason?: string | null;
  created_by?: string | null;
  created_at?: string | null;
};

export type StockMutationResult = {
  inventory: Inventory;
  transaction: InventoryTransaction;
};

export type CreateProductInput = {
  category_id: string;
  sku: string;
  name: string;
  slug?: string;
  description?: string;
  unit?: string;
  origin?: string;
  moq?: number;
  lead_time_days?: number;
  status?: string;
  is_featured?: boolean;
};

export type UpdateProductInput = Partial<CreateProductInput> & {
  status?: string;
};

export type CreatePriceInput = {
  min_quantity: number;
  max_quantity?: number | null;
  unit_price: string;
  currency?: string;
  is_active?: boolean;
};

export type StockInput = {
  quantity: string;
  reason?: string;
  reference_type?: string;
  reference_id?: string;
};

export type CreateCategoryInput = {
  name: string;
  slug?: string;
  description?: string;
  parent_category_id?: string | null;
  display_order?: number;
  is_active?: boolean;
};

export const PRODUCT_UNITS = [
  "piece",
  "box",
  "carton",
  "kg",
  "liter",
  "unit",
] as const;

export const catalogApi = {
  listCategories: (params?: {
    parent_category_id?: string;
    active_only?: boolean;
    page?: number;
    page_size?: number;
  }) => apiClient.getPage<Category>("/catalog/categories", { params }),

  getCategory: (id: string) => apiClient.get<Category>(`/catalog/categories/${id}`),

  createCategory: (body: CreateCategoryInput) =>
    apiClient.post<Category>("/catalog/categories", body),

  updateCategory: (
    id: string,
    body: Partial<CreateCategoryInput> & { clear_parent?: boolean },
  ) => apiClient.patch<Category>(`/catalog/categories/${id}`, body),

  deleteCategory: (id: string) =>
    apiClient.delete<{ deleted: boolean }>(`/catalog/categories/${id}`),

  uploadCategoryImage: (categoryId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.upload<Category>(
      `/catalog/categories/${categoryId}/image`,
      form,
    );
  },

  clearCategoryImage: (categoryId: string) =>
    apiClient.delete<Category>(`/catalog/categories/${categoryId}/image`),

  listProducts: (params?: {
    supplier_business_id?: string;
    category_id?: string;
    status?: string;
    q?: string;
    featured?: boolean;
    include_details?: boolean;
    page?: number;
    page_size?: number;
  }) => apiClient.getPage<Product>("/catalog/products", { params }),

  getProduct: (id: string) => apiClient.get<Product>(`/catalog/products/${id}`),

  createProduct: (body: CreateProductInput) =>
    apiClient.post<Product>("/catalog/products", body),

  updateProduct: (id: string, body: UpdateProductInput) =>
    apiClient.patch<Product>(`/catalog/products/${id}`, body),

  deactivateProduct: (id: string) =>
    apiClient.delete<{ deactivated: boolean }>(`/catalog/products/${id}`),

  listPrices: (productId: string) =>
    apiClient.get<ProductPrice[]>(`/catalog/products/${productId}/prices`),

  createPrice: (productId: string, body: CreatePriceInput) =>
    apiClient.post<ProductPrice>(`/catalog/products/${productId}/prices`, body),

  updatePrice: (
    productId: string,
    priceId: string,
    body: Partial<CreatePriceInput> & { clear_max_quantity?: boolean },
  ) =>
    apiClient.patch<ProductPrice>(
      `/catalog/products/${productId}/prices/${priceId}`,
      body,
    ),

  deletePrice: (productId: string, priceId: string) =>
    apiClient.delete<{ deleted: boolean }>(
      `/catalog/products/${productId}/prices/${priceId}`,
    ),

  uploadProductImage: (
    productId: string,
    file: File,
    options?: { alt_text?: string; is_primary?: boolean },
  ) => {
    const form = new FormData();
    form.append("file", file);
    if (options?.alt_text) form.append("alt_text", options.alt_text);
    if (options?.is_primary) form.append("is_primary", "true");
    return apiClient.upload<ProductImage>(
      `/catalog/products/${productId}/images`,
      form,
    );
  },

  setPrimaryProductImage: (productId: string, imageId: string) =>
    apiClient.patch<ProductImage>(
      `/catalog/products/${productId}/images/${imageId}/primary`,
    ),

  deleteProductImage: (productId: string, imageId: string) =>
    apiClient.delete<{ deleted: boolean }>(
      `/catalog/products/${productId}/images/${imageId}`,
    ),

  getInventory: (productId: string) =>
    apiClient.get<Inventory>(`/inventory/products/${productId}`),

  addStock: (productId: string, body: StockInput) =>
    apiClient.post<StockMutationResult>(
      `/inventory/products/${productId}/stock`,
      body,
    ),

  reserveStock: (productId: string, body: StockInput) =>
    apiClient.post<StockMutationResult>(
      `/inventory/products/${productId}/reserve`,
      body,
    ),

  releaseStock: (productId: string, body: StockInput) =>
    apiClient.post<StockMutationResult>(
      `/inventory/products/${productId}/release`,
      body,
    ),

  saleStock: (productId: string, body: StockInput) =>
    apiClient.post<StockMutationResult>(
      `/inventory/products/${productId}/sale`,
      body,
    ),

  listTransactions: (
    productId: string,
    params?: { page?: number; page_size?: number },
  ): Promise<PaginatedResult<InventoryTransaction>> =>
    apiClient.getPage<InventoryTransaction>(
      `/inventory/products/${productId}/transactions`,
      { params },
    ),
};
