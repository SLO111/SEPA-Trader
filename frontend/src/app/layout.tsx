import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { THEME_BOOT } from "@/lib/theme";

export const metadata: Metadata = {
  title: { default: "Vnicorn Investments", template: "%s · Vnicorn Investments" },
  description: "Daily trade ideas with stop, trim and target, a Move Detector for major moves, pro charts, alerts and company insight.",
};

export const viewport = { width: "device-width", initialScale: 1, themeColor: "#0b0e14" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
