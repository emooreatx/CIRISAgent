import './globals.css';
import type { ReactNode } from 'react';
import Link from 'next/link';

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <aside className="sidebar">
          <h2>CIRIS</h2>
          <nav>
            <ul>
              <li><Link href="/">Home</Link></li>
              <li><Link href="/audit">Audit</Link></li>
              <li><Link href="/comms">Communications</Link></li>
              <li><Link href="/memory">Memory</Link></li>
              <li><Link href="/tools">Tools</Link></li>
              <li><Link href="/wa">WA</Link></li>
            </ul>
          </nav>
        </aside>
        <main>{children}</main>
      </body>
    </html>
  );
}
