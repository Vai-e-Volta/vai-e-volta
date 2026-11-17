import { useState } from 'react';
import { MAX_TAGS, MAX_TAG_LENGTH, normalizeTag } from '../utils/listingValidation';
import { inputClassName } from './FormField';

/**
 * Tags do anúncio (RN-57): até 5, com até 30 caracteres. Enter ou vírgula adiciona;
 * tags iguais sem diferença de maiúsculas e acentos não se repetem. Recebe id e aria-*
 * do FormField.
 */
export default function TagInput({ tags, onChange, onError, ...inputProps }) {
  const [draft, setDraft] = useState('');
  const full = tags.length >= MAX_TAGS;

  function add() {
    const tag = draft.trim().replace(/\s+/g, ' ');
    if (!tag) return;
    if (tag.length > MAX_TAG_LENGTH) {
      onError(`Cada tag tem até ${MAX_TAG_LENGTH} caracteres.`);
      return;
    }
    if (tags.some((current) => normalizeTag(current) === normalizeTag(tag))) {
      onError('Essa tag já foi adicionada.');
      setDraft('');
      return;
    }
    onError('');
    onChange([...tags, tag]);
    setDraft('');
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault();
      add();
    } else if (event.key === 'Backspace' && !draft && tags.length > 0) {
      onChange(tags.slice(0, -1));
    }
  }

  function remove(tag) {
    onError('');
    onChange(tags.filter((current) => current !== tag));
  }

  return (
    <div className="flex flex-col gap-2">
      {tags.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Tags adicionadas">
          {tags.map((tag) => (
            <li
              key={tag}
              className="flex items-center gap-1 rounded-full border border-line bg-panel py-1 pl-3 pr-1 text-sm text-slate-200"
            >
              {tag}
              <button
                type="button"
                onClick={() => remove(tag)}
                aria-label={`Remover tag ${tag}`}
                className="flex h-6 w-6 items-center justify-center rounded-full text-slate-400 hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                <span aria-hidden="true">✕</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <input
        {...inputProps}
        value={draft}
        onChange={(event) => setDraft(event.target.value.replace(',', ''))}
        onKeyDown={handleKeyDown}
        onBlur={add}
        disabled={full}
        maxLength={MAX_TAG_LENGTH + 1}
        placeholder={full ? `Limite de ${MAX_TAGS} tags` : 'Ex.: furadeira'}
        className={inputClassName}
      />
    </div>
  );
}
