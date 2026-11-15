import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import ListingForm from '../components/ListingForm';
import { useAuth } from '../hooks/useAuth';
import { createListing } from '../services/listings';
import { EMPTY_LISTING, pickupFromUser, toListingFormData } from '../utils/listingValidation';

/** Criar anúncio (F-38): local de retirada vem do cadastro (RN-59); envio em multipart. */
export default function NewListingPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  async function handleSubmit(values, photos) {
    const listing = await createListing(
      toListingFormData(
        values,
        photos.map((photo) => photo.file),
      ),
    );
    // O novo anúncio aparece no feed e em "Meus anúncios".
    await queryClient.invalidateQueries({ queryKey: ['listings'] });
    await queryClient.invalidateQueries({ queryKey: ['me', 'listings'] });
    navigate(listing?.id ? `/itens/${listing.id}` : '/alugueis', { state: { created: true } });
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
          Anunciar item
        </h1>
        <p className="mt-2 text-slate-400">
          Conte o que você tem para alugar, quanto custa por dia e quando está disponível.
        </p>
      </div>
      <ListingForm
        initialValues={{ ...EMPTY_LISTING, ...pickupFromUser(user) }}
        submitLabel="Publicar anúncio"
        pendingLabel="Publicando…"
        onSubmit={handleSubmit}
      />
    </div>
  );
}
