import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router';
import ListingForm from '../components/ListingForm';
import LoadingScreen from '../components/LoadingScreen';
import { getListing, updateListing } from '../services/listings';
import { listingToForm, toListingUpdateFormData } from '../utils/listingValidation';

const ACTIVE_RENTAL_MESSAGE =
  'Este anúncio tem um aluguel aceito em andamento ou agendado que ficaria fora da nova ' +
  'janela. Ajuste as datas para que esse período continue dentro dela.';

function Message({ title, text, id }) {
  return (
    <section className="py-16 text-center">
      <h1 className="text-2xl font-semibold tracking-tight text-white">{title}</h1>
      <p className="mt-2 text-slate-400">{text}</p>
      <Link
        to={id ? `/itens/${id}` : '/'}
        className="mt-8 inline-block rounded-lg bg-accent px-5 py-2.5 font-semibold text-ink hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
      >
        {id ? 'Ver anúncio' : 'Voltar ao início'}
      </Link>
    </section>
  );
}

/** Editar anúncio (F-41): só o dono (RN-60); a edição vale para novas propostas (RN-61). */
export default function EditListingPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
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
  if (!listing.is_owner) {
    return (
      <Message
        title="Você não pode editar este anúncio"
        text="Só o dono edita o anúncio."
        id={id}
      />
    );
  }

  const initial = listingToForm(listing);

  async function handleSubmit(values, photos) {
    const data = toListingUpdateFormData(values, initial.values, photos, initial.photos);
    if (data) {
      try {
        await updateListing(id, data);
      } catch (caught) {
        if (caught.code === 'LISTING_HAS_ACTIVE_RENTAL') {
          caught.message = ACTIVE_RENTAL_MESSAGE;
          caught.fields = { available_until: 'Um aluguel aceito ficaria fora da janela.' };
        }
        throw caught;
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['listing', id] }),
        queryClient.invalidateQueries({ queryKey: ['listings'] }),
        queryClient.invalidateQueries({ queryKey: ['me', 'listings'] }),
      ]);
    }
    navigate(`/itens/${id}`, { state: data ? { updated: true } : undefined });
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
          Editar anúncio
        </h1>
        <p className="mt-2 text-slate-400">
          As mudanças valem para novas propostas. Propostas e aluguéis já enviados mantêm os dados
          de quando foram feitos.
        </p>
      </div>
      <ListingForm
        key={listing.id}
        initialValues={initial.values}
        initialPhotos={initial.photos}
        submitLabel="Salvar alterações"
        pendingLabel="Salvando…"
        onSubmit={handleSubmit}
        editing
      />
    </div>
  );
}
