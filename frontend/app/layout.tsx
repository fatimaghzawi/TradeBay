import { ToastProvider } from "@/components/ui/Toast";
import { AuthProvider } from "@/providers/AuthProvider";
import { LiveUpdatesProvider } from "@/providers/LiveUpdatesProvider";
import { QueryProvider } from "@/providers/QueryProvider";
import { ThemeProvider } from "@/providers/ThemeProvider";
import type { Metadata } from "next";
import { Figtree, Fraunces, Great_Vibes } from "next/font/google";
import type { ReactNode } from "react";
import "./globals.css";
import "./deal-room.css";
import "./commercial-docs.css";
import "./order-tracking.css";
import "./commerce.css";
import "./design-system.css";

const figtree = Figtree({
  subsets: ["latin"],
  variable: "--font-figtree",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
});

const signature = Great_Vibes({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-signature",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "TradeBay",
    template: "%s · TradeBay",
  },
  description:
    "The trusted B2B marketplace for Lebanese businesses to source, compare, and negotiate with verified suppliers.",
};

const themeBootScript = `
(function(){
  try {
    var t = localStorage.getItem('tradebay-theme');
    if (t !== 'dark' && t !== 'light') t = 'dark';
    document.documentElement.classList.toggle('dark', t === 'dark');
    document.documentElement.dataset.theme = t;
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      className={`${figtree.variable} ${fraunces.variable} ${signature.variable} dark`}
      data-theme="dark"
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className="antialiased">
        <ThemeProvider>
          <QueryProvider>
            <AuthProvider>
              <LiveUpdatesProvider>
                <ToastProvider>{children}</ToastProvider>
              </LiveUpdatesProvider>
            </AuthProvider>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
