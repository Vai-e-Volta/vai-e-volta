import { useId } from 'react';
import { formatCurrency, maskDate } from '../utils/format';
import { proposalSummary } from '../utils/rentalPeriod';
import { inputClassName } from './FormField';

function DateField({ label, name, value, error, onChange }) {
  const id = useId();
  const errorId = `${id}-erro`;
  return (
    <div className="min-w-0 flex-1">
      <label htmlFor={id} className="text-sm font-medium text-slate-200">
        {label}
      </label>
      <input
        id={id}
        name={name}
        value={value}
        onChange={(event) => onChange(maskDate(event.target.value))}
        inputMode="numeric"
        placeholder="dd/mm/aaaa"
        autoComplete="off"
        maxLength={10}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        className={`mt-1.5 ${inputClassName}`}
      />
      {error && (
        <p id={errorId} className="mt-1.5 text-sm text-red-300">
          {error}
        </p>
      )}
    </div>
  );
}

/**
 * Escolha do período (F-32) com início e fim em dd/mm/aaaa e o resumo "N dia(s) · R$ X"
 * (F-33). O resumo é só um auxílio visual; o valor vale como estimativa (RN-43).
 */
export default function DateRangePicker({ value, errors = {}, dailyPrice, onChange }) {
  const summary = proposalSummary(value, dailyPrice);
  return (
    <div>
      <div className="flex flex-col gap-4 sm:flex-row">
        <DateField
          label="Início"
          name="start_date"
          value={value.start}
          error={errors.start_date}
          onChange={(start) => onChange({ ...value, start })}
        />
        <DateField
          label="Fim"
          name="end_date"
          value={value.end}
          error={errors.end_date}
          onChange={(end) => onChange({ ...value, end })}
        />
      </div>
      <p aria-live="polite" className="mt-4 text-slate-300">
        {summary ? (
          <>
            <span className="font-semibold text-white">
              {summary.days === 1 ? '1 dia' : `${summary.days} dias`} ·{' '}
              {formatCurrency(summary.total)}
            </span>{' '}
            <span className="text-sm text-slate-400">valor estimado, sem cobrança pelo app</span>
          </>
        ) : (
          <span className="text-sm text-slate-400">
            Escolha as datas para ver o total estimado.
          </span>
        )}
      </p>
    </div>
  );
}
