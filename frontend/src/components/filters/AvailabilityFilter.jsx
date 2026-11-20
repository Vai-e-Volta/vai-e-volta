import { useId } from 'react';
import { AVAILABILITY_OPTIONS } from '../../utils/feedFilters';
import FilterSection from './FilterSection';

/** Disponibilidade (F-21, RN-28): todos, disponíveis agora ou atualmente alugados. */
export default function AvailabilityFilter({ value, onChange }) {
  const name = useId();
  const current = value || AVAILABILITY_OPTIONS[0].value;
  return (
    <FilterSection title="Disponibilidade">
      <div className="flex flex-col gap-1">
        {AVAILABILITY_OPTIONS.map((option, index) => (
          <label
            key={option.value}
            className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-1.5 text-slate-200 hover:bg-white/5"
          >
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={current === option.value}
              onChange={() => onChange(index === 0 ? null : option.value)}
              className="h-4 w-4 shrink-0 accent-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            />
            {option.label}
          </label>
        ))}
      </div>
    </FilterSection>
  );
}
