/** Marca: um arco que vai (pêssego) e outro que volta (menta). */
export default function BrandMark({ className = 'h-7 w-7' }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden="true" className={className}>
      <path
        d="M5 16C5 8.5 10 5 16 5s11 3.5 11 11"
        stroke="var(--color-accent)"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path
        d="M27 16c0 7.5-5 11-11 11S5 23.5 5 16"
        stroke="var(--color-flow)"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path
        d="m23.5 13 3.5 3.5 3.5-3.5"
        stroke="var(--color-accent)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M8.5 19 5 15.5 1.5 19"
        stroke="var(--color-flow)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
