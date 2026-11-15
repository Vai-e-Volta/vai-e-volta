import { useQuery } from '@tanstack/react-query';
import { useId, useRef, useState } from 'react';
import { getCategories } from '../services/listings';
import { todayIso } from '../utils/format';
import {
  LISTING_FIELD_ORDER,
  MAX_DESCRIPTION,
  MAX_TITLE,
  listingServerErrors,
  validateListing,
} from '../utils/listingValidation';
import { UF_OPTIONS, formatCep } from '../utils/registrationValidation';
import FormField, { inputClassName } from './FormField';
import PhotoUploader from './PhotoUploader';
import TagInput from './TagInput';

const MASKS = { pickup_cep: formatCep };

function Section({ title, description, children }) {
  const headingId = useId();
  return (
    <section
      aria-labelledby={headingId}
      className="rounded-2xl border border-line bg-surface p-5 sm:p-7"
    >
      <h2 id={headingId} className="text-lg font-semibold tracking-tight text-white">
        {title}
      </h2>
      {description && <p className="mt-1 text-sm text-slate-400">{description}</p>}
      <div className="mt-5 flex flex-col gap-5">{children}</div>
    </section>
  );
}

/**
 * Formulário do anúncio (seção 11.3), usado na criação e na edição. `onSubmit(values,
 * photos)` deve devolver uma Promise; se ela falhar com ApiError, os erros aparecem
 * em cada campo.
 */
export default function ListingForm({
  initialValues,
  initialPhotos = [],
  submitLabel,
  pendingLabel,
  onSubmit,
}) {
  const formRef = useRef(null);
  const [values, setValues] = useState(initialValues);
  const [photos, setPhotos] = useState(initialPhotos);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const today = todayIso();

  const categories = useQuery({
    queryKey: ['categories'],
    queryFn: getCategories,
    staleTime: Infinity,
  });

  function clearError(field) {
    if (!errors[field]) return;
    setErrors((current) => {
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  function handleChange(event) {
    const { name, value } = event.target;
    const mask = MASKS[name];
    setValues((current) => ({ ...current, [name]: mask ? mask(value) : value }));
    clearError(name);
  }

  function showErrors(nextErrors, summary) {
    setErrors(nextErrors);
    setFormError(summary);
    const first = LISTING_FIELD_ORDER.find((field) => nextErrors[field]);
    const element = first && formRef.current?.elements.namedItem(first);
    element?.focus?.();
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = validateListing(values, photos.length, { today });
    if (Object.keys(nextErrors).length > 0) {
      showErrors(nextErrors, 'Revise os campos destacados.');
      return;
    }
    setErrors({});
    setFormError('');
    setSubmitting(true);
    try {
      await onSubmit(values, photos);
    } catch (error) {
      const fieldErrors = listingServerErrors(error);
      showErrors(
        fieldErrors,
        Object.keys(fieldErrors).length > 0 ? 'Revise os campos destacados.' : error.message,
      );
    } finally {
      setSubmitting(false);
    }
  }

  const fieldProps = (name) => ({
    name,
    value: values[name],
    onChange: handleChange,
    className: inputClassName,
  });

  return (
    <form ref={formRef} noValidate onSubmit={handleSubmit} className="flex flex-col gap-6">
      {formError && (
        <div
          role="alert"
          className="rounded-lg border border-red-400/40 bg-red-400/10 px-4 py-3 text-sm text-red-200"
        >
          {formError}
        </div>
      )}

      <Section title="Fotos">
        <PhotoUploader
          photos={photos}
          onChange={(next) => {
            setPhotos(next);
            clearError('photos');
          }}
          error={errors.photos}
        />
      </Section>

      <Section title="Sobre o item">
        <FormField label="Nome do item" error={errors.title} required>
          <input {...fieldProps('title')} maxLength={MAX_TITLE} />
        </FormField>
        <FormField
          label="Descrição"
          error={errors.description}
          hint={`${values.description.length} de ${MAX_DESCRIPTION} caracteres`}
          required
        >
          <textarea {...fieldProps('description')} rows={5} maxLength={MAX_DESCRIPTION} />
        </FormField>
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField
            label="Categoria"
            error={
              errors.category_id ??
              (categories.isError ? 'Não foi possível carregar as categorias.' : undefined)
            }
            required
          >
            <select {...fieldProps('category_id')} disabled={categories.isPending}>
              <option value="">{categories.isPending ? 'Carregando…' : 'Escolha'}</option>
              {(categories.data ?? []).map((category) => (
                <option key={category.id} value={String(category.id)}>
                  {category.name}
                </option>
              ))}
            </select>
          </FormField>
          <FormField
            label="Tags"
            error={errors.tags}
            hint="Até 5 tags. Enter ou vírgula para adicionar."
          >
            <TagInput
              name="tags"
              tags={values.tags}
              onChange={(tags) => {
                setValues((current) => ({ ...current, tags }));
                clearError('tags');
              }}
              onError={(message) =>
                setErrors((current) => {
                  const next = { ...current };
                  if (message) next.tags = message;
                  else delete next.tags;
                  return next;
                })
              }
            />
          </FormField>
        </div>
      </Section>

      <Section
        title="Valor e disponibilidade"
        description="O item fica disponível entre o início e o fim da janela; cada aluguel dura no máximo o prazo escolhido."
      >
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField
            label="Valor por dia (R$)"
            error={errors.daily_price}
            hint="De R$ 1,00 a R$ 5.000,00."
            required
          >
            <input {...fieldProps('daily_price')} inputMode="decimal" placeholder="25,00" />
          </FormField>
          <FormField label="Máximo de dias por aluguel" error={errors.max_days} required>
            <input {...fieldProps('max_days')} type="number" inputMode="numeric" min={1} step={1} />
          </FormField>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField label="Disponível a partir de" error={errors.available_from} required>
            <input {...fieldProps('available_from')} type="date" />
          </FormField>
          <FormField label="Disponível até" error={errors.available_until} required>
            <input
              {...fieldProps('available_until')}
              type="date"
              min={values.available_from || today}
            />
          </FormField>
        </div>
      </Section>

      <Section
        title="Local de retirada"
        description="Vem do seu cadastro e pode ser trocado neste anúncio. Na página do item aparecem rua, bairro e cidade; número e complemento só para quem tiver o aluguel aceito."
      >
        <div className="grid gap-5 sm:grid-cols-[10rem_1fr]">
          <FormField label="CEP" error={errors.pickup_cep} required>
            <input {...fieldProps('pickup_cep')} inputMode="numeric" placeholder="00000-000" />
          </FormField>
          <FormField label="Rua" error={errors.pickup_street} required>
            <input {...fieldProps('pickup_street')} maxLength={100} />
          </FormField>
        </div>
        <div className="grid gap-5 sm:grid-cols-[8rem_1fr]">
          <FormField label="Número" error={errors.pickup_number} required>
            <input {...fieldProps('pickup_number')} maxLength={10} />
          </FormField>
          <FormField label="Complemento" error={errors.pickup_complement}>
            <input {...fieldProps('pickup_complement')} maxLength={60} />
          </FormField>
        </div>
        <div className="grid gap-5 sm:grid-cols-[1fr_1fr_6rem]">
          <FormField label="Bairro" error={errors.pickup_neighborhood} required>
            <input {...fieldProps('pickup_neighborhood')} maxLength={100} />
          </FormField>
          <FormField label="Cidade" error={errors.pickup_city} required>
            <input {...fieldProps('pickup_city')} maxLength={100} />
          </FormField>
          <FormField label="UF" error={errors.pickup_state} required>
            <select {...fieldProps('pickup_state')}>
              <option value="">--</option>
              {UF_OPTIONS.map((uf) => (
                <option key={uf} value={uf}>
                  {uf}
                </option>
              ))}
            </select>
          </FormField>
        </div>
      </Section>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-accent px-6 py-3 font-semibold text-ink shadow-lg shadow-accent/10 transition-colors hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:opacity-60"
        >
          {submitting ? pendingLabel : submitLabel}
        </button>
      </div>
    </form>
  );
}
