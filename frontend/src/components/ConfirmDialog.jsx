import { useEffect, useId, useRef } from 'react';

const FOCUSABLE =
  'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

/**
 * Diálogo de confirmação acessível: foco inicial em "Cancelar" (ou no primeiro campo,
 * quando há campos em `children`), Esc fecha, Tab circula dentro do diálogo e o foco
 * volta ao elemento de origem ao fechar. Enter num campo confirma.
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
  children,
}) {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef(null);
  const cancelRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const previouslyFocused = document.activeElement;
    const firstField = dialogRef.current?.querySelector('input, select, textarea');
    (firstField ?? cancelRef.current)?.focus();
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

  function handleSubmit(event) {
    event.preventDefault();
    if (!busy) onConfirm();
  }

  const confirmColor = destructive
    ? 'bg-red-400 text-ink hover:bg-red-300 focus-visible:ring-red-400'
    : 'bg-accent text-ink hover:bg-accent-hover focus-visible:ring-accent';

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-4 backdrop-blur-sm sm:items-center">
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        onKeyDown={handleKeyDown}
        className="w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-2xl shadow-black/50"
      >
        <h2 id={titleId} className="text-lg font-semibold tracking-tight text-white">
          {title}
        </h2>
        {description && (
          <p id={descriptionId} className="mt-2 text-slate-300">
            {description}
          </p>
        )}
        <form noValidate onSubmit={handleSubmit}>
          {children && <div className="mt-5">{children}</div>}
          <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button
              ref={cancelRef}
              type="button"
              onClick={onCancel}
              disabled={busy}
              className="rounded-lg border border-flow/40 px-4 py-2.5 font-medium text-flow hover:bg-flow/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-flow focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-60"
            >
              {cancelLabel}
            </button>
            <button
              type="submit"
              disabled={busy}
              className={`rounded-lg px-4 py-2.5 font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-60 ${confirmColor}`}
            >
              {confirmLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
