import { useQuery } from '@tanstack/react-query';
import { useId, useState } from 'react';
import { getPriceRanges } from '../../services/listings';
import { formatCurrency } from '../../utils/format';
import { parsePriceRange, priceToInput } from '../../utils/feedFilters';
import FilterSection from './FilterSection';
import { chipClassName, smallInputClassName } from './filterStyles';

function PriceInput({ label, value, error, onChange }) {
  const id = useId();
  const errorId = `${id}-erro`;
  return (
    <div className="min-w-0 flex-1">
      <label htmlFor={id} className="text-xs text-slate-400">
        {label}
      </label>
      <input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        inputMode="decimal"
        placeholder="R$ 0,00"
        autoComplete="off"
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        className={`mt-1 ${smallInputClassName}`}
      />
      {error && (
        <p id={errorId} className="mt-1 text-xs text-red-300">
          {error}
        </p>
      )}
    </div>
  );
}

/**
 * Faixa de preço por dia (F-18) e atalhos por tercis (F-19, RN-27). Os atalhos somem
 * quando a API devolve lista vazia (menos de 3 anúncios ativos).
 */
export default function PriceFilter({ min, max, onChange }) {
  const [text, setText] = useState({ min: priceToInput(min), max: priceToInput(max) });
  const [synced, setSynced] = useState({ min, max });
  const [errors, setErrors] = useState({});

  // A URL mudou por fora (atalho, limpar, voltar): os campos mostram os novos valores.
  if (synced.min !== min || synced.max !== max) {
    setSynced({ min, max });
    setText({ min: priceToInput(min), max: priceToInput(max) });
    setErrors({});
  }

  const { data: ranges = [] } = useQuery({
    queryKey: ['price-ranges'],
    queryFn: getPriceRanges,
    staleTime: 5 * 60 * 1000,
  });

  function handleSubmit(event) {
    event.preventDefault();
    const result = parsePriceRange(text.min, text.max);
    setErrors(result.errors);
    if (Object.keys(result.errors).length === 0) onChange(result.values);
  }

  function update(field, value) {
    setText((current) => ({ ...current, [field]: value }));
    const key = field === 'min' ? 'price_min' : 'price_max';
    if (errors[key]) setErrors((current) => ({ ...current, [key]: undefined }));
  }

  const isRange = (range) => range.min === min && range.max === max;
  const hasPrice = Boolean(min || max);

  return (
    <FilterSection
      title="Preço por dia"
      onClear={hasPrice ? () => onChange({ price_min: null, price_max: null }) : null}
    >
      {ranges.length > 0 && (
        <ul className="mb-4 flex flex-col gap-1.5">
          {ranges.map((range) => (
            <li key={range.label}>
              <button
                type="button"
                aria-pressed={isRange(range)}
                onClick={() =>
                  onChange(
                    isRange(range)
                      ? { price_min: null, price_max: null }
                      : { price_min: range.min, price_max: range.max },
                  )
                }
                className={`flex w-full items-baseline justify-between gap-2 rounded-lg px-3 py-2 text-left ${chipClassName(isRange(range))}`}
              >
                {range.label}
                <span className="sr-only">
                  {`: de ${formatCurrency(range.min)} a ${formatCurrency(range.max)}`}
                </span>
                <span aria-hidden="true" className="whitespace-nowrap text-xs opacity-75">
                  {formatCurrency(range.min)}–{formatCurrency(range.max)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <form noValidate onSubmit={handleSubmit}>
        <div className="flex gap-2">
          <PriceInput
            label="Mínimo"
            value={text.min}
            error={errors.price_min}
            onChange={(value) => update('min', value)}
          />
          <PriceInput
            label="Máximo"
            value={text.max}
            error={errors.price_max}
            onChange={(value) => update('max', value)}
          />
        </div>
        <button
          type="submit"
          className="mt-3 w-full rounded-lg border border-accent/50 px-3 py-2 text-sm font-medium text-accent hover:bg-accent/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          Aplicar preço
        </button>
      </form>
    </FilterSection>
  );
}
