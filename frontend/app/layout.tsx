import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'CashFlow Radar',
  description: 'Корпоративный учет денежных потоков и прогнозирование NetCF',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang='ru'>
      <body>{children}</body>
    </html>
  )
}
