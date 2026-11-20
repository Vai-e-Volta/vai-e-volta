import { useId, useState } from 'react';
import { parsePeriod } from '../../utils/feedFilters';
import { isoToBrDate, maskDate } from '../../utils/format';
import FilterSection from './FilterSection';
import { smallInputClassName } from './filterStyles';

function DateInput({ label, value, error, onChange }) {
  const id = useId();
  const errorId = `${id}-erro`;
  return (
    <div className="min-w-0">
      <label htmlFor={id} className="text-xs text-slate-400">
        {label}
      </label>
      <input
        id={id}
        value={value}
        onChange={(event) => onChange(maskDate(event.target.value))}
        inputMode="numeric"
        placeholder="dd/mm/aaaa"
        autoComplete="off"
        maxLength={10}
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
 * Período desejado (F-22): "preciso de … até …". Só vale com as duas datas (RN-29); a
 * tela usa dd/mm/aaaa, qualquer que seja o idioma do navegador, e envia AAAA-MM-DD.
 */
export default function PeriodFilter({ from, until, onChange }) {
  const [text, setText] = useState({ from: isoToBrDate(from), until: isoToBrDate(until) });
  const [synced, setSynced] = useState({ from, until });
  const [errors, setErrors] = useState({});

  // A URL mudou por fora (limpar, voltar): os campos mostram os novos valores.
  if (synced.from !== from || synced.until !== until) {
    setSynced({ from, until });
    setText({ from: isoToBrDate(from), until: isoToBrDate(until) });
    setErrors({});
  }

  function update(field, value) {
    setText((current) => ({ ...current, [field]: value }));
    setErrors({});
  }

  function handleSubmit(event) {
    event.preventDefault();
    const result = parsePeriod(text.from, text.until);
    setErrors(result.errors);
    if (Object.keys(result.errors).length === 0) onChange(result.values);
  }

  return (
    <FilterSection
      title="Período"
      onClear={from || until ? () => onChange({ needed_from: null, needed_until: null }) : null}
    >
      <form noValidate onSubmit={handleSubmit} className="flex flex-col gap-3">
        <DateInput
          label="Preciso de"
          value={text.from}
          error={errors.needed_from}
          onChange={(value) => update('from', value)}
        />
        <DateInput
          label="até"
          value={text.until}
          error={errors.needed_until}
          onChange={(value) => update('until', value)}
        />
        <button
          type="submit"
          className="w-full rounded-lg border border-accent/50 px-3 py-2 text-sm font-medium text-accent hover:bg-accent/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          Aplicar período
        </button>
      </form>
    </FilterSection>
  );
}
