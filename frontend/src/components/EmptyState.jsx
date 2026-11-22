import { Link } from 'react-router';
import BrandMark from './BrandMark';

/**
 * Feed sem resultados (F-27): mensagem clara, botão para limpar os filtros (quando há
 * algum) e atalho para anunciar. "Limpar filtros" volta ao feed completo, por isso usa a
 * cor de volta; "Anunciar item" segue em frente, na cor de vai.
 */
export default function EmptyState({ hasFilters, onClearFilters }) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-line bg-panel px-6 py-12 text-center">
      <BrandMark className="h-12 w-12 opacity-80" />
      <h2 className="mt-5 text-lg font-semibold tracking-tight text-white">
        Nenhum item encontrado
      </h2>
      <p className="mt-2 max-w-md text-slate-400">
        {hasFilters
          ? 'Nenhum anúncio combina com a busca e os filtros escolhidos. Tente tirar alguns filtros.'
          : 'Ainda não há itens para alugar. Que tal anunciar o primeiro?'}
      </p>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        {hasFilters && (
          <button
            type="button"
            onClick={onClearFilters}
            className="rounded-lg border border-flow/40 px-5 py-2.5 font-medium text-flow hover:bg-flow/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-flow"
          >
            Limpar filtros
          </button>
        )}
        <Link
          to="/anunciar"
          className="rounded-lg bg-accent px-5 py-2.5 font-semibold text-ink hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-panel"
        >
          Anunciar item
        </Link>
      </div>
    </div>
  );
}
