import { useQuery } from '@tanstack/react-query';
import { useId, useState } from 'react';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { getTags } from '../../services/listings';
import { normalizeTag } from '../../utils/listingValidation';
import FilterSection from './FilterSection';
import { chipClassName, smallInputClassName } from './filterStyles';

const TAG_SEARCH_DELAY_MS = 300;

/**
 * Filtro por tags (F-17): as mais usadas em destaque e um campo para buscar outras.
 * Várias marcadas combinam com OU (RN-26).
 */
export default function TagFilter({ selected, onChange }) {
  const inputId = useId();
  const [text, setText] = useState('');
  const term = useDebouncedValue(text.trim(), TAG_SEARCH_DELAY_MS);

  const { data: options = [], isFetching } = useQuery({
    queryKey: ['tags', term],
    queryFn: () => getTags(term),
    staleTime: 5 * 60 * 1000,
  });

  const isSelected = (tag) => selected.some((item) => normalizeTag(item) === normalizeTag(tag));

  function toggle(tag) {
    onChange(
      isSelected(tag)
        ? selected.filter((item) => normalizeTag(item) !== normalizeTag(tag))
        : [...selected, tag],
    );
  }

  // Tags marcadas que não estão na lista atual continuam visíveis para desmarcar.
  const extra = selected.filter(
    (tag) => !options.some((option) => normalizeTag(option) === normalizeTag(tag)),
  );

  return (
    <FilterSection title="Tags" onClear={selected.length > 0 ? () => onChange([]) : null}>
      <label htmlFor={inputId} className="sr-only">
        Buscar tag
      </label>
      <input
        id={inputId}
        type="search"
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="Buscar tag"
        autoComplete="off"
        maxLength={30}
        className={smallInputClassName}
      />
      <p className="mt-3 text-xs text-slate-400">
        <span>{term ? `Tags com “${term}”` : 'Mais usadas'}</span>
        {isFetching && <span> · buscando…</span>}
      </p>
      <ul className="mt-2 flex flex-wrap gap-2">
        {[...extra, ...options].map((tag) => (
          <li key={normalizeTag(tag)}>
            <button
              type="button"
              aria-pressed={isSelected(tag)}
              onClick={() => toggle(tag)}
              className={`rounded-full px-3 py-1 ${chipClassName(isSelected(tag))}`}
            >
              {tag}
            </button>
          </li>
        ))}
      </ul>
      {!isFetching && term && options.length === 0 && (
        <p className="mt-2 text-sm text-slate-400">Nenhuma tag encontrada.</p>
      )}
    </FilterSection>
  );
}
