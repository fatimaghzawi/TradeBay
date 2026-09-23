"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type ShellContextValue = {
  mobileNavOpen: boolean;
  setMobileNavOpen: (open: boolean) => void;
  toggleMobileNav: () => void;
  mobileSpaceOpen: boolean;
  setMobileSpaceOpen: (open: boolean) => void;
  toggleMobileSpace: () => void;
};

const ShellContext = createContext<ShellContextValue | null>(null);

export function ShellProvider({ children }: { children: ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [mobileSpaceOpen, setMobileSpaceOpen] = useState(false);
  const value = useMemo(
    () => ({
      mobileNavOpen,
      setMobileNavOpen,
      toggleMobileNav: () => {
        setMobileNavOpen((v) => !v);
        setMobileSpaceOpen(false);
      },
      mobileSpaceOpen,
      setMobileSpaceOpen,
      toggleMobileSpace: () => {
        setMobileSpaceOpen((v) => !v);
        setMobileNavOpen(false);
      },
    }),
    [mobileNavOpen, mobileSpaceOpen],
  );
  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>;
}

export function useShell() {
  const ctx = useContext(ShellContext);
  if (!ctx) throw new Error("useShell must be used within ShellProvider");
  return ctx;
}
