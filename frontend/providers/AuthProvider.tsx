"use client";

import { ApiError } from "@/lib/api/client";
import { authApi, type AuthUser } from "@/lib/api/authApi";
import {
  identityApi,
  type Business,
} from "@/lib/api/identityApi";
import { AUTH_QUERY_KEY, BUSINESSES_QUERY_KEY } from "@/lib/auth/session";
import { ROUTES } from "@/lib/constants";
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
  business: Business | null;
  businesses: Business[];
  permissions: string[];
  isLoading: boolean;
  isAuthenticated: boolean;
  setBusiness: (business: Business | null) => void;
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
  "/trust",
  "/settings",
  "/admin",
  "/conversations",
  "/ai-sourcing",
  "/business-planner",
];

function isProtectedPath(pathname: string): boolean {
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
  });

  const businessesQuery = useQuery({
    queryKey: BUSINESSES_QUERY_KEY,
    queryFn: () => identityApi.listBusinesses(),
    enabled: !!sessionQuery.data?.user,
    retry: false,
  });

  const user = sessionQuery.data?.user ?? null;
  const permissions = sessionQuery.data?.permissions ?? [];
  const businesses = useMemo(
    () => businessesQuery.data?.businesses ?? [],
    [businessesQuery.data?.businesses],
  );

  const business = useMemo(() => {
    const activeId = sessionQuery.data?.active_business?.id;
    if (activeId) {
      return businesses.find((item) => item.id === activeId) ?? sessionQuery.data?.active_business ?? null;
    }
    return businesses[0] ?? null;
  }, [businesses, sessionQuery.data?.active_business]);

  const isLoading =
    sessionQuery.isLoading ||
    (sessionQuery.isSuccess && !!user && businessesQuery.isLoading);

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

  const setBusiness = useCallback(
    (next: Business | null) => {
      if (!next) return;
      void identityApi.switchBusiness(next.id).then(() => {
        void queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY });
      });
    },
    [queryClient],
  );

  const hasPermission = useCallback(
    (code: string) => permissions.includes(code),
    [permissions],
  );

  const refreshSession = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY });
    await queryClient.invalidateQueries({ queryKey: BUSINESSES_QUERY_KEY });
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
      isLoading,
      isAuthenticated: !!user,
      setBusiness,
      hasPermission,
      refreshSession,
      logout,
    }),
    [
      user,
      business,
      businesses,
      permissions,
      isLoading,
      setBusiness,
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
