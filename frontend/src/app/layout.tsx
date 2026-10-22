import type { Metadata, Viewport } from "next";
import { Fraunces, Manrope } from "next/font/google";
import { DemoMount } from "@/components/layout/demo-mount";
import { ToastProvider } from "@/components/ui/toast";
import { AuthProvider } from "@/lib/auth/auth-context";
import "./globals.css";

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  axes: ["opsz", "SOFT"],
  style: ["normal", "italic"],
  display: "swap",
});

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Reiki UFRB — sessões de Reiki com agendamento semanal",
    template: "%s · Reiki UFRB",
  },
  description:
    "Conheça o Reiki, consulte a agenda semanal e inscreva-se em sessões de bem-estar. Informações claras sobre como participar.",
};

export const viewport: Viewport = {
  themeColor: "#fbf8f2",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${fraunces.variable} ${manrope.variable} h-full`}>
      <body className="flex min-h-full flex-col">
        <a
          href="#conteudo"
          className="sr-only z-[100] rounded-full bg-forest-800 px-5 py-3 font-semibold text-ivory focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
        >
          Pular para o conteúdo
        </a>
        <AuthProvider>
          <ToastProvider>
            <DemoMount />
            {children}
          </ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
