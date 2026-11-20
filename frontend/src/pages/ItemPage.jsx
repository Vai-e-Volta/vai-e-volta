import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router';
import LoadingScreen from '../components/LoadingScreen';
import OwnerListingActions from '../components/OwnerListingActions';
import PhotoGallery from '../components/PhotoGallery';
import ProposalPanel from '../components/ProposalPanel';
import { getBookedPeriods, getListing } from '../services/listings';
import { formatCurrency, isoToBrDate } from '../utils/format';

const STATUS_LABELS = { active: 'Ativo', paused: 'Pausado', deleted: 'Excluído' };
const SITUATION_LABELS = { available: 'Disponível', rented: 'Alugado' };

const backLinkClassName =
  'mt-8 inline-block rounded-lg bg-flow px-5 py-2.5 font-semibold text-ink hover:bg-flow-hover ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-flow ' +
  'focus-visible:ring-offset-2 focus-visible:ring-offset-canvas';

function Message({ title, text }) {
  return (
    <section className="py-16 text-center">
      <h1 className="text-2xl font-semibold tracking-tight text-white">{title}</h1>
      <p className="mt-2 text-slate-400">{text}</p>
      <Link to="/" className={backLinkClassName}>
        Voltar ao feed
      </Link>
    </section>
  );
}

function Detail({ label, children }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</dt>
      <dd className="mt-1 text-slate-100">{children}</dd>
    </div>
  );
}

function categoryName(listing) {
  return typeof listing.category === 'string' ? listing.category : listing.category?.name;
}

function tagNames(listing) {
  return (listing.tags ?? []).map((tag) => (typeof tag === 'string' ? tag : tag.name));
}

/**
 * Local de retirada (RN-35): rua, bairro e cidade para todos; número e complemento só
 * vêm da API para o dono e para o locatário com aluguel aceito.
 */
function pickupAddress(listing) {
  const street = [listing.pickup_street, listing.pickup_number].filter(Boolean).join(', ');
  const line1 = [street, listing.pickup_complement].filter(Boolean).join(' – ');
  const city = [listing.pickup_city, listing.pickup_state].filter(Boolean).join('/');
  const line2 = [listing.pickup_neighborhood, city].filter(Boolean).join(', ');
  return [line1, line2].filter(Boolean);
}

function BookedPeriods({ id }) {
  const {
    data: periods,
    error,
    isPending,
  } = useQuery({
    queryKey: ['listing', id, 'booked-periods'],
    queryFn: () => getBookedPeriods(id),
  });

  return (
    <section aria-labelledby="periodos" className="rounded-xl border border-line bg-panel p-5">
      <h2 id="periodos" className="font-semibold text-white">
        Períodos reservados
      </h2>
      {isPending && <p className="mt-2 text-sm text-slate-400">Carregando…</p>}
      {error && <p className="mt-2 text-sm text-red-300">{error.message}</p>}
      {periods && periods.length === 0 && (
        <p className="mt-2 text-sm text-slate-400">Nenhum período reservado até agora.</p>
      )}
      {periods && periods.length > 0 && (
        <ul className="mt-3 flex flex-col gap-2">
          {periods.map((period) => (
            <li
              key={`${period.start_date}-${period.end_date}`}
              className="flex items-center gap-2 text-sm tabular-nums text-slate-200"
            >
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-accent" />
              {isoToBrDate(period.start_date)} a {isoToBrDate(period.end_date)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** Visão do dono (F-31): situação do anúncio e ações de editar, pausar e excluir. */
function OwnerPanel({ listing, onDeleted }) {
  const status = STATUS_LABELS[listing.status];
  const situation = SITUATION_LABELS[listing.situation];
  return (
    <section
      aria-labelledby="seu-anuncio"
      className="rounded-xl border border-accent/40 bg-accent/5 p-5"
    >
      <h2 id="seu-anuncio" className="font-semibold text-white">
        Seu anúncio
      </h2>
      <p className="mt-1 text-sm text-slate-300">
        {[status, situation].filter(Boolean).join(' · ') || 'Você é o dono deste anúncio.'}
      </p>
      <div className="mt-4">
        <OwnerListingActions listing={listing} onDeleted={onDeleted} />
      </div>
    </section>
  );
}

/**
 * Página do item (F-28 a F-31): galeria, dados do anúncio, períodos reservados,
 * anunciante e proposta de aluguel. O dono não vê o botão de proposta (RN-33); anúncio
 * pausado, excluído ou de conta excluída aparece como indisponível para os outros (RN-34).
 */
export default function ItemPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const {
    data: listing,
    error,
    isPending,
  } = useQuery({
    queryKey: ['listing', id],
    queryFn: () => getListing(id),
    retry: (failureCount, queryError) => queryError.status >= 500 && failureCount < 1,
  });

  if (isPending) return <LoadingScreen />;
  if (error?.status === 404) {
    return <Message title="Anúncio não encontrado" text="Este anúncio não existe." />;
  }
  if (error) return <Message title="Não foi possível carregar o anúncio" text={error.message} />;
  if (listing.unavailable && !listing.is_owner) {
    return (
      <Message
        title="Anúncio indisponível"
        text="Este anúncio foi pausado ou excluído e não recebe propostas no momento."
      />
    );
  }

  const tags = tagNames(listing);
  const owner = listing.owner?.username ?? listing.owner_username;
  const address = pickupAddress(listing);

  return (
    // No celular a ordem é foto, dados e descrição; no computador a descrição fica
    // embaixo da foto e os dados na coluna da direita.
    <article className="grid gap-8 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:grid-rows-[auto_1fr]">
      <div className="lg:col-start-1 lg:row-start-1">
        <PhotoGallery photos={listing.photos ?? []} title={listing.title} />
      </div>

      <div className="flex flex-col gap-6 lg:col-start-2 lg:row-span-2 lg:row-start-1">
        <header>
          {categoryName(listing) && (
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              {categoryName(listing)}
            </p>
          )}
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
            {listing.title}
          </h1>
          <p className="mt-3 text-2xl text-accent">
            <span className="font-semibold">{formatCurrency(listing.daily_price)}</span>{' '}
            <span className="text-base text-slate-400">por dia</span>
          </p>
          {tags.length > 0 && (
            <ul aria-label="Tags" className="mt-4 flex flex-wrap gap-2">
              {tags.map((tag) => (
                <li
                  key={tag}
                  className="rounded-full border border-line px-3 py-1 text-sm text-slate-300"
                >
                  {tag}
                </li>
              ))}
            </ul>
          )}
        </header>

        {listing.is_owner ? (
          <OwnerPanel
            listing={listing}
            onDeleted={() => navigate('/', { replace: true, state: { listingDeleted: true } })}
          />
        ) : (
          <ProposalPanel listing={listing} />
        )}

        <dl className="grid gap-4 rounded-xl border border-line bg-panel p-5 sm:grid-cols-2">
          <Detail label="Prazo máximo">
            {listing.max_days === 1 ? '1 dia' : `${listing.max_days} dias`} por aluguel
          </Detail>
          <Detail label="Disponível">
            {isoToBrDate(listing.available_from)} a {isoToBrDate(listing.available_until)}
          </Detail>
          <Detail label="Retirada">
            {address.map((line) => (
              <span key={line} className="block">
                {line}
              </span>
            ))}
          </Detail>
          {owner && (
            <Detail label="Anunciante">
              <Link
                to={`/usuarios/${encodeURIComponent(owner)}`}
                className="rounded text-accent hover:text-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                @{owner}
              </Link>
            </Detail>
          )}
        </dl>

        <BookedPeriods id={id} />
      </div>

      <section aria-labelledby="descricao" className="lg:col-start-1 lg:row-start-2">
        <h2 id="descricao" className="font-semibold text-white">
          Descrição
        </h2>
        <p className="mt-2 whitespace-pre-line text-slate-300">{listing.description}</p>
      </section>
    </article>
  );
}
