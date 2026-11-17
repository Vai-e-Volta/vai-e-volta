import { Link, Outlet } from 'react-router';
import BrandMark from './BrandMark';

/** Layout base das telas logadas: mobile-first, cabeçalho no topo e conteúdo centralizado. */
export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#conteudo"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-accent focus:px-3 focus:py-2 focus:font-semibold focus:text-ink"
      >
        Pular para o conteúdo
      </a>
      <header className="border-b border-line bg-surface/80 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center px-4">
          <Link
            to="/"
            className="inline-flex items-center gap-2.5 rounded-md text-lg font-semibold tracking-tight text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
          >
            <BrandMark />
            Vai e Volta
          </Link>
        </div>
      </header>
      <main id="conteudo" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:py-10">
        <Outlet />
      </main>
    </div>
  );
}
