import type { Metadata } from "next";
import { Comfortaa } from "next/font/google";

import { Header } from "@/widgets/header/ui/header";
import "./globals.css";

const comfortaa = Comfortaa({
  subsets: ["cyrillic", "latin"],
  variable: "--font-comfortaa",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CashFlow Radar",
  description: "Корпоративная ликвидность без слепых зон",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body className={comfortaa.variable}>
        <Header />
        {children}
      </body>
    </html>
  );
}
