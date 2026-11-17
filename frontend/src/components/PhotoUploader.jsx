import { useEffect, useId, useRef, useState } from 'react';
import { MAX_PHOTOS, MAX_PHOTO_MB, PHOTO_TYPES, photoFileError } from '../utils/listingValidation';

let nextKey = 0;

/** Foto nova escolhida no computador, com prévia local. */
function photoFromFile(file) {
  nextKey += 1;
  return { key: `new-${nextKey}`, file, url: URL.createObjectURL(file) };
}

const iconButtonBase =
  'flex h-8 w-8 items-center justify-center rounded-md bg-black/60 hover:bg-black/80 ' +
  'focus-visible:outline-none focus-visible:ring-2 disabled:opacity-40';
const iconButtonClassName = `${iconButtonBase} text-white focus-visible:ring-accent`;
// Mover para a esquerda volta (menta); para a direita vai (pêssego).
const backButtonClassName = `${iconButtonBase} font-bold text-flow focus-visible:ring-flow`;
const forwardButtonClassName = `${iconButtonBase} font-bold text-accent focus-visible:ring-accent`;

/**
 * Fotos do anúncio (RN-56): de 1 a 5, JPEG, PNG ou WebP, até 5 MB cada, com prévia,
 * reordenação e escolha da capa (a primeira). Cada item é { key, url, file? } (fotos já
 * salvas têm `id` e não têm `file`). Com `newAfterSaved`, usado na edição, as fotos
 * novas ficam sempre depois das salvas, como a API grava (seção 10).
 */
export default function PhotoUploader({ photos, onChange, error, newAfterSaved = false }) {
  const inputId = useId();
  const errorId = `${inputId}-error`;
  const hintId = `${inputId}-hint`;
  const [rejected, setRejected] = useState([]);
  const latest = useRef(photos);
  useEffect(() => {
    latest.current = photos;
  }, [photos]);

  // Libera as prévias locais quando o componente sai da tela.
  useEffect(
    () => () => {
      for (const photo of latest.current) if (photo.file) URL.revokeObjectURL(photo.url);
    },
    [],
  );

  function handleFiles(event) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = '';
    const messages = [];
    const accepted = [];
    for (const file of files) {
      const message = photoFileError(file);
      if (message) messages.push(message);
      else if (photos.length + accepted.length >= MAX_PHOTOS) {
        messages.push(`${file.name}: o anúncio já tem ${MAX_PHOTOS} fotos.`);
      } else accepted.push(photoFromFile(file));
    }
    setRejected(messages);
    if (accepted.length > 0) onChange([...photos, ...accepted]);
  }

  // Na edição, uma foto nova não passa à frente de uma salva, e vice-versa.
  function canMove(index, target) {
    if (target < 0 || target >= photos.length) return false;
    if (!newAfterSaved) return true;
    const isNew = (position) => Boolean(photos[position].file);
    const [from, to] = index < target ? [index, target] : [target, index];
    return photos.slice(from, to + 1).every((_, offset) => isNew(from + offset) === isNew(index));
  }

  function move(index, target) {
    const next = [...photos];
    const [photo] = next.splice(index, 1);
    next.splice(target, 0, photo);
    onChange(next);
  }

  function remove(index) {
    const photo = photos[index];
    if (photo.file) URL.revokeObjectURL(photo.url);
    setRejected([]);
    onChange(photos.filter((_, position) => position !== index));
  }

  const messages = [error, ...rejected].filter(Boolean);
  const full = photos.length >= MAX_PHOTOS;

  return (
    <div className="flex flex-col gap-3">
      <p id={hintId} className="text-sm text-slate-400">
        De 1 a {MAX_PHOTOS} fotos, JPEG, PNG ou WebP, até {MAX_PHOTO_MB} MB cada. A primeira é a
        capa.{newAfterSaved && ' Fotos novas entram depois das que já estão no anúncio.'}
      </p>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {photos.map((photo, index) => {
          const label = `foto ${index + 1}`;
          return (
            <li
              key={photo.key}
              className="group relative aspect-square overflow-hidden rounded-xl border border-line bg-panel"
            >
              <img
                src={photo.url}
                alt={`Prévia da ${label}${index === 0 ? ' (capa)' : ''}`}
                className="h-full w-full object-cover"
              />
              {index === 0 && (
                <span className="absolute left-2 top-2 rounded-md bg-accent px-2 py-0.5 text-xs font-semibold text-ink">
                  Capa
                </span>
              )}
              <div className="absolute inset-x-0 bottom-0 flex justify-between gap-1 bg-gradient-to-t from-black/70 to-transparent p-2">
                <div className="flex gap-1">
                  <button
                    type="button"
                    onClick={() => move(index, index - 1)}
                    disabled={!canMove(index, index - 1)}
                    aria-label={`Mover ${label} para a esquerda`}
                    className={backButtonClassName}
                  >
                    <span aria-hidden="true">←</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => move(index, index + 1)}
                    disabled={!canMove(index, index + 1)}
                    aria-label={`Mover ${label} para a direita`}
                    className={forwardButtonClassName}
                  >
                    <span aria-hidden="true">→</span>
                  </button>
                </div>
                <div className="flex gap-1">
                  {index > 0 && canMove(index, 0) && (
                    <button
                      type="button"
                      onClick={() => move(index, 0)}
                      aria-label={`Usar ${label} como capa`}
                      className={iconButtonClassName}
                    >
                      <span aria-hidden="true">★</span>
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => remove(index)}
                    aria-label={`Remover ${label}`}
                    className={iconButtonClassName}
                  >
                    <span aria-hidden="true">✕</span>
                  </button>
                </div>
              </div>
            </li>
          );
        })}
        {!full && (
          <li className="aspect-square">
            <input
              id={inputId}
              name="photos"
              type="file"
              accept={PHOTO_TYPES.join(',')}
              multiple
              onChange={handleFiles}
              aria-invalid={messages.length > 0 ? true : undefined}
              aria-describedby={[hintId, messages.length > 0 ? errorId : null]
                .filter(Boolean)
                .join(' ')}
              className="peer sr-only"
            />
            <label
              htmlFor={inputId}
              className="flex h-full cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed border-line text-center text-sm text-slate-300 transition-colors hover:border-accent hover:text-white peer-focus-visible:border-accent peer-focus-visible:ring-2 peer-focus-visible:ring-accent/40 peer-aria-[invalid=true]:border-red-400"
            >
              <span aria-hidden="true" className="text-2xl text-accent">
                +
              </span>
              Adicionar fotos
              <span className="text-xs text-slate-400">
                {photos.length} de {MAX_PHOTOS}
              </span>
            </label>
          </li>
        )}
      </ul>
      {messages.length > 0 && (
        <div id={errorId} className="text-sm text-red-300">
          {messages.map((message) => (
            <p key={message}>{message}</p>
          ))}
        </div>
      )}
    </div>
  );
}
