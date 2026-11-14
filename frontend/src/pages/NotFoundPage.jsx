import { Link } from 'react-router';

export default function NotFoundPage() {
  return (
    <section className="py-16 text-center">
      <p className="text-sm font-semibold uppercase tracking-[0.3em] text-accent">404</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white">
        Página não encontrada
      </h1>
      <p className="mt-2 text-slate-400">O endereço acessado não existe.</p>
      <Link
        to="/"
        className="mt-8 inline-block rounded-lg bg-accent px-5 py-2.5 font-semibold text-ink hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
      >
        Voltar ao início
      </Link>
    </section>
  );
}
