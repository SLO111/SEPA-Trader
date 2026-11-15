import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "SEPA Trader",
  description: "Platformă de analiză și trading pe acțiuni",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ro">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
