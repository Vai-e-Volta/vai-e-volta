import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router';
import LoadingScreen from '../components/LoadingScreen';
import { getPublicProfile } from '../services/users';
import { formatCurrency, formatDate } from '../utils/format';

/**
 * Perfil público (F-10): nome de usuário, bairro e cidade, membro desde e anúncios
 * ativos. A API só devolve dados públicos (RN-15).
 */
export default function UserProfilePage() {
  const { username } = useParams();
  const {
    data: profile,
    error,
    isPending,
  } = useQuery({
    queryKey: ['users', username],
    queryFn: () => getPublicProfile(username),
    retry: (failureCount, queryError) => queryError.status !== 404 && failureCount < 1,
  });

  if (isPending) return <LoadingScreen />;

  if (error) {
    const notFound = error.status === 404;
    return (
      <section className="py-16 text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-white">
          {notFound ? 'Perfil não encontrado' : 'Não foi possível carregar o perfil'}
        </h1>
        <p className="mt-2 text-slate-400">
          {notFound ? 'Esta pessoa não existe ou não está mais no Vai e Volta.' : error.message}
        </p>
        <Link
          to="/"
          className="mt-8 inline-block rounded-lg bg-flow px-5 py-2.5 font-semibold text-ink hover:bg-flow-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-flow focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
        >
          Voltar ao início
        </Link>
      </section>
    );
  }

  const listings = profile.listings ?? [];
  const place = [profile.neighborhood, profile.city].filter(Boolean).join(', ');
  const memberSince = formatDate(profile.created_at);

  return (
    <section>
      <header className="flex items-center gap-4">
        <span
          aria-hidden="true"
          className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full border border-line bg-panel text-2xl font-semibold uppercase text-accent"
        >
          {profile.username.charAt(0)}
        </span>
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold tracking-tight text-white sm:text-3xl">
            @{profile.username}
          </h1>
          <dl className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-400">
            {place && (
              <div className="flex gap-1">
                <dt className="sr-only">Local</dt>
                <dd>{place}</dd>
              </div>
            )}
            {memberSince && (
              <div className="flex gap-1">
                <dt>Membro desde</dt>
                <dd>{memberSince}</dd>
              </div>
            )}
          </dl>
        </div>
      </header>

      <h2 className="mt-10 text-lg font-semibold text-white">
        Anúncios ativos <span className="font-normal text-slate-400">({listings.length})</span>
      </h2>
      {listings.length === 0 ? (
        <p className="mt-3 rounded-lg border border-line bg-panel px-4 py-6 text-center text-slate-400">
          Nenhum anúncio ativo no momento.
        </p>
      ) : (
        <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {listings.map((listing) => (
            <li key={listing.id}>
              <Link
                to={`/itens/${listing.id}`}
                className="flex h-full flex-col rounded-xl border border-line bg-panel p-4 transition-colors hover:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
              >
                <span className="font-medium text-white">{listing.title}</span>
                <span className="mt-auto pt-3 text-sm text-accent">
                  {formatCurrency(listing.daily_price)}{' '}
                  <span className="text-slate-400">por dia</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
