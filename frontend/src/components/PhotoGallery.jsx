import { useState } from 'react';
import { photoUrl } from '../services/listings';

/** Galeria do anúncio (F-28): foto grande e miniaturas para trocar. A primeira é a capa. */
export default function PhotoGallery({ photos, title }) {
  const [current, setCurrent] = useState(0);
  const index = Math.min(current, Math.max(photos.length - 1, 0));

  if (photos.length === 0) {
    return (
      <div className="flex aspect-[4/3] items-center justify-center rounded-2xl border border-line bg-surface text-slate-400">
        Sem foto
      </div>
    );
  }

  return (
    <div>
      <div className="aspect-[4/3] overflow-hidden rounded-2xl border border-line bg-surface">
        <img
          src={photoUrl(photos[index])}
          alt={`${title}, foto ${index + 1} de ${photos.length}`}
          className="h-full w-full object-cover"
        />
      </div>
      {photos.length > 1 && (
        <ul className="mt-3 grid grid-cols-5 gap-2">
          {photos.map((photo, position) => (
            <li key={photo.id ?? position}>
              <button
                type="button"
                onClick={() => setCurrent(position)}
                aria-label={`Ver foto ${position + 1}`}
                aria-current={position === index ? 'true' : undefined}
                className={`block aspect-square w-full overflow-hidden rounded-lg border-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                  position === index
                    ? 'border-accent'
                    : 'border-transparent opacity-70 hover:opacity-100'
                }`}
              >
                <img src={photoUrl(photo)} alt="" className="h-full w-full object-cover" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
