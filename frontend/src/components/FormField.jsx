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
      <label htmlFor={inputId} className="text-sm font-medium text-slate-800">
        {label}
        {required ? (
          <span aria-hidden="true" className="text-red-700">
            {' '}
            *
          </span>
        ) : (
          <span className="font-normal text-slate-600"> (opcional)</span>
        )}
      </label>
      {input}
      {hint && (
        <p id={hintId} className="text-xs text-slate-600">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}

/** Classes padrão para inputs, compartilhadas pelos formulários. */
export const inputClassName =
  'w-full rounded-md border border-slate-400 bg-white px-3 py-2 text-base text-slate-900 ' +
  'placeholder:text-slate-500 focus:border-emerald-700 focus:outline-2 focus:outline-offset-1 ' +
  'focus:outline-emerald-700 aria-[invalid=true]:border-red-700';
