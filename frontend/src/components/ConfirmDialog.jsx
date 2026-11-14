import { useEffect, useId, useRef } from 'react';

const FOCUSABLE =
  'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

/**
 * Diálogo de confirmação acessível: foco inicial em "Cancelar", Esc fecha,
 * Tab circula dentro do diálogo e o foco volta ao elemento de origem ao fechar.
 */
export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirmar',
  cancelLabel = 'Cancelar',
  destructive = false,
  busy = false,
  onConfirm,
  onCancel,
}) {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef(null);
  const cancelRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const previouslyFocused = document.activeElement;
    cancelRef.current?.focus();
    return () => {
      if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus();
    };
  }, [open]);

  if (!open) return null;

  function handleKeyDown(event) {
    if (event.key === 'Escape') {
      event.stopPropagation();
      if (!busy) onCancel();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = dialogRef.current.querySelectorAll(FOCUSABLE);
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  const confirmColor = destructive
    ? 'bg-red-700 hover:bg-red-800 focus-visible:outline-red-700'
    : 'bg-emerald-700 hover:bg-emerald-800 focus-visible:outline-emerald-700';

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/50 p-4 sm:items-center">
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        onKeyDown={handleKeyDown}
        className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl"
      >
        <h2 id={titleId} className="text-lg font-semibold text-slate-900">
          {title}
        </h2>
        {description && (
          <p id={descriptionId} className="mt-2 text-slate-700">
            {description}
          </p>
        )}
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-md border border-slate-400 px-4 py-2 font-medium text-slate-800 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700 disabled:opacity-60"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={`rounded-md px-4 py-2 font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-60 ${confirmColor}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
