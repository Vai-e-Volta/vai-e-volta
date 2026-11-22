import { useEffect, useId, useRef, useState } from 'react';
import { inputClassName } from './FormField';

export const SEARCH_DELAY_MS = 400;

/**
 * Busca pelo nome (F-16): consulta depois de uma espera curta sem digitar, ou na hora
 * com Enter. O valor vem da URL e acompanha mudanças nela (voltar no navegador).
 */
export default function SearchField({ value, onSearch, delay = SEARCH_DELAY_MS }) {
  const id = useId();
  const [text, setText] = useState(value);
  const [synced, setSynced] = useState(value);
  const onSearchRef = useRef(onSearch);

  useEffect(() => {
    onSearchRef.current = onSearch;
  }, [onSearch]);

  // A URL mudou por fora (voltar, limpar filtros): o campo passa a mostrar o novo valor.
  if (value !== synced) {
    setSynced(value);
    setText(value);
  }

  useEffect(() => {
    if (text.trim() === value) return undefined;
    const timer = setTimeout(() => onSearchRef.current(text.trim()), delay);
    return () => clearTimeout(timer);
  }, [text, value, delay]);

  function handleSubmit(event) {
    event.preventDefault();
    if (text.trim() !== value) onSearchRef.current(text.trim());
  }

  return (
    <form role="search" onSubmit={handleSubmit}>
      <label htmlFor={id} className="sr-only">
        Buscar pelo nome do item
      </label>
      <div className="relative">
        <svg
          aria-hidden="true"
          viewBox="0 0 20 20"
          fill="none"
          className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400"
        >
          <circle cx="9" cy="9" r="5.5" stroke="currentColor" strokeWidth="1.8" />
          <path d="m13.5 13.5 3 3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
        <input
          id={id}
          type="search"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Buscar pelo nome do item"
          autoComplete="off"
          enterKeyHint="search"
          maxLength={100}
          className={`${inputClassName} pl-11`}
        />
      </div>
    </form>
  );
}
