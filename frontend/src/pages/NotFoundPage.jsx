import { Link } from 'react-router';

export default function NotFoundPage() {
  return (
    <section className="py-12 text-center">
      <h1 className="text-2xl font-bold text-slate-900">Página não encontrada</h1>
      <p className="mt-2 text-slate-700">O endereço acessado não existe.</p>
      <Link
        to="/"
        className="mt-6 inline-block rounded-md bg-emerald-700 px-4 py-2 font-medium text-white hover:bg-emerald-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700"
      >
        Voltar ao início
      </Link>
    </section>
  );
}
