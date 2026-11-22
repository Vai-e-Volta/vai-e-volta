import AvailabilityFilter from './filters/AvailabilityFilter';
import CategoryFilter from './filters/CategoryFilter';
import FavoritesFilter from './filters/FavoritesFilter';
import PeriodFilter from './filters/PeriodFilter';
import PriceFilter from './filters/PriceFilter';
import TagFilter from './filters/TagFilter';

/**
 * Barra lateral de filtros do feed (seção 11.3): favoritos (F-26), categorias (F-25),
 * tags (F-17), preço (F-18, F-19), disponibilidade (F-21) e período (F-22). Tipos diferentes combinam com E; dentro do mesmo tipo vale OU
 * (RN-26). Cada bloco devolve só as chaves que mudou.
 */
export default function FilterSidebar({ filters, onChange }) {
  return (
    <div className="flex flex-col gap-5">
      <FavoritesFilter
        checked={filters.favorites === 'true'}
        onChange={(favorites) => onChange({ favorites })}
      />
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
      <AvailabilityFilter
        value={filters.availability ?? ''}
        onChange={(availability) => onChange({ availability })}
      />
      <PeriodFilter
        from={filters.needed_from ?? ''}
        until={filters.needed_until ?? ''}
        onChange={(period) => onChange(period)}
      />
    </div>
  );
}
