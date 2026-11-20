import CategoryFilter from './filters/CategoryFilter';
import PriceFilter from './filters/PriceFilter';
import TagFilter from './filters/TagFilter';

/**
 * Barra lateral de filtros do feed (seção 11.3): categorias (F-25), tags (F-17) e
 * preço (F-18, F-19). Tipos diferentes combinam com E; dentro do mesmo tipo vale OU
 * (RN-26). Cada bloco devolve só as chaves que mudou.
 */
export default function FilterSidebar({ filters, onChange }) {
  return (
    <div className="flex flex-col gap-5">
      <CategoryFilter
        selected={filters.categories ?? []}
        onChange={(categories) => onChange({ categories })}
      />
      <TagFilter selected={filters.tags ?? []} onChange={(tags) => onChange({ tags })} />
      <PriceFilter
        min={filters.price_min ?? ''}
        max={filters.price_max ?? ''}
        onChange={(price) => onChange(price)}
      />
    </div>
  );
}
