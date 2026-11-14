import { cloneElement, isValidElement, useId } from 'react';

/**
 * Campo de formulário com rótulo e mensagem de erro associados (seção 11.5).
 * Recebe um único elemento de entrada como filho e liga id, aria-invalid e
 * aria-describedby a ele.
 */
export default function FormField({ label, error, hint, required = false, children, className }) {
  const generatedId = useId();
  const child = isValidElement(children) ? children : null;
  const inputId = child?.props.id ?? `field-${generatedId}`;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined;

  const input = child
    ? cloneElement(child, {
        id: inputId,
        required: child.props.required ?? required,
        'aria-invalid': error ? true : undefined,
        'aria-describedby': describedBy,
      })
    : children;

  return (
    <div className={['flex flex-col gap-1', className].filter(Boolean).join(' ')}>
      <label htmlFor={inputId} className="text-sm font-medium text-slate-200">
        {label}
        {required ? (
          <span aria-hidden="true" className="text-accent">
            {' '}
            *
          </span>
        ) : (
          <span className="font-normal text-slate-400"> (opcional)</span>
        )}
      </label>
      {input}
      {hint && (
        <p id={hintId} className="text-xs text-slate-400">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-sm text-red-300">
          {error}
        </p>
      )}
    </div>
  );
}

/** Classes padrão para inputs, compartilhadas pelos formulários. */
export const inputClassName =
  'w-full rounded-lg border border-line bg-field px-3.5 py-2.5 text-base text-white ' +
  'placeholder:text-slate-400 transition-colors hover:border-slate-500 ' +
  'focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30 ' +
  'aria-[invalid=true]:border-red-400 aria-[invalid=true]:focus:ring-red-400/30';
