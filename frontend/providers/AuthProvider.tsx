"use client";

import { ApiError } from "@/lib/api/client";
import { authApi, type AuthUser } from "@/lib/api/authApi";
import { identityApi, type Business } from "@/lib/api/identityApi";
import { AUTH_QUERY_KEY, BUSINESSES_QUERY_KEY } from "@/lib/auth/session";
import { ROUTES } from "@/lib/constants";
import { isGuestAllowedPath } from "@/lib/guestAccess";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from "react";

type AuthContextValue = {
  user: AuthUser | null;
  /** Active company from session — not client-switched. */
  business: Business | null;
  /** Memberships for gate checks only (e.g. one-company create). Not a switcher. */
  businesses: Business[];
  permissions: string[];
  roleName: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  hasPermission: (code: string) => boolean;
  refreshSession: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const PROTECTED_PREFIXES = [
  "/dashboard",
  "/catalog",
  "/procurement",
  "/finance",
  "/settings",
  "/admin",
  "/conversations",
  "/negotiations",
  "/ai-sourcing",
  "/business-planner",
  "/members",
  "/invitations",
  "/roles",
  "/businesses",
  "/audit",
  "/orders",
  "/quotations",
  "/inventory",
  "/suppliers",
];

function isProtectedPath(pathname: string): boolean {
  if (isGuestAllowedPath(pathname)) return false;
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();

  const sessionQuery = useQuery({
    queryKey: AUTH_QUERY_KEY,
    queryFn: () => authApi.me(),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const businessesQuery = useQuery({
    queryKey: BUSINESSES_QUERY_KEY,
    queryFn: () => identityApi.listBusinesses(),
    enabled: !!sessionQuery.data?.user,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const user = sessionQuery.data?.user ?? null;
  const permissions = sessionQuery.data?.permissions ?? [];
  const roleName =
    sessionQuery.data?.role_name ??
    sessionQuery.data?.active_business?.role_name ??
    null;
  const businesses = useMemo(
    () => businessesQuery.data?.businesses ?? [],
    [businessesQuery.data?.businesses],
  );

  const business = useMemo(() => {
    const active = sessionQuery.data?.active_business ?? null;
    if (!active?.id) return null;
    return businesses.find((item) => item.id === active.id) ?? active;
  }, [businesses, sessionQuery.data?.active_business]);

  const isLoading =
    sessionQuery.isLoading ||
    (sessionQuery.isFetching && !sessionQuery.data && !sessionQuery.isError);

  useEffect(() => {
    if (
      !sessionQuery.isLoading &&
      sessionQuery.isError &&
      sessionQuery.error instanceof ApiError &&
      sessionQuery.error.status === 401 &&
      isProtectedPath(pathname)
    ) {
      router.replace(ROUTES.login);
    }
  }, [
    pathname,
    router,
    sessionQuery.error,
    sessionQuery.isError,
    sessionQuery.isLoading,
  ]);

  const hasPermission = useCallback(
    (code: string) => permissions.includes(code),
    [permissions],
  );

  const refreshSession = useCallback(async () => {
    void queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY });
    void queryClient.invalidateQueries({ queryKey: BUSINESSES_QUERY_KEY });
  }, [queryClient]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      queryClient.clear();
      router.replace(ROUTES.login);
    }
  }, [queryClient, router]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      business,
      businesses,
      permissions,
      roleName,
      isLoading,
      isAuthenticated: !!user,
      hasPermission,
      refreshSession,
      logout,
    }),
    [
      user,
      business,
      businesses,
      permissions,
      roleName,
      isLoading,
      hasPermission,
      refreshSession,
      logout,
    ],
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
