import { useRef } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router';
import BrandMark from './BrandMark';
import LoopIllustration from './LoopIllustration';

const TABS = [
  { to: '/login', label: 'Entrar', id: 'tab-login' },
  { to: '/cadastro', label: 'Criar conta', id: 'tab-cadastro' },
];

const PANEL_ID = 'auth-panel';

/**
 * Tela de acesso: cartão dividido com o formulário à esquerda e o conceito à direita
 * (no desktop). As abas continuam sendo as rotas /login e /cadastro (seção 11.1).
 */
export default function AuthLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const tabRefs = useRef([]);
  const selectedIndex = Math.max(
    TABS.findIndex((tab) => tab.to === location.pathname),
    0,
  );

  // Padrão de abas (WAI-ARIA): setas, Home e End trocam de aba.
  function handleKeyDown(event) {
    const last = TABS.length - 1;
    const next = {
      ArrowRight: selectedIndex === last ? 0 : selectedIndex + 1,
      ArrowLeft: selectedIndex === 0 ? last : selectedIndex - 1,
      Home: 0,
      End: last,
    }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    navigate(TABS[next].to, { state: location.state });
    tabRefs.current[next]?.focus();
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-8 sm:py-12">
      <div className="w-full max-w-5xl overflow-hidden rounded-2xl border border-line bg-surface shadow-2xl shadow-black/50 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="px-5 py-8 sm:px-10 sm:py-10">
          <Link
            to="/login"
            className="inline-flex items-center gap-2.5 rounded-md text-lg font-semibold tracking-tight text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
          >
            <BrandMark />
            Vai e Volta
          </Link>

          <div
            role="tablist"
            aria-label="Acesso à conta"
            className="mt-8 flex gap-6 border-b border-line"
          >
            {TABS.map((tab, index) => {
              const selected = index === selectedIndex;
              return (
                <Link
                  key={tab.to}
                  ref={(element) => {
                    tabRefs.current[index] = element;
                  }}
                  to={tab.to}
                  state={location.state}
                  role="tab"
                  id={tab.id}
                  aria-selected={selected}
                  aria-controls={PANEL_ID}
                  tabIndex={selected ? 0 : -1}
                  onKeyDown={handleKeyDown}
                  className={[
                    'relative -mb-px rounded-t-md pb-3 text-sm font-semibold transition-colors',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent',
                    'focus-visible:ring-offset-2 focus-visible:ring-offset-surface',
                    selected
                      ? 'text-white after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:rounded-full after:bg-accent'
                      : 'text-slate-400 hover:text-slate-200',
                  ].join(' ')}
                >
                  {tab.label}
                </Link>
              );
            })}
          </div>

          <div
            role="tabpanel"
            id={PANEL_ID}
            aria-labelledby={TABS[selectedIndex].id}
            className="pt-8"
          >
            <Outlet />
          </div>
        </div>

        <aside className="relative hidden flex-col justify-center gap-10 overflow-hidden border-l border-line bg-panel px-10 py-12 lg:flex">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full border border-line/60"
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -bottom-32 -left-20 h-80 w-80 rounded-full border border-line/40"
          />
          <LoopIllustration />
          <div className="relative">
            <p className="text-2xl font-semibold leading-snug tracking-tight text-white">
              O que fica parado na sua casa pode resolver o dia de alguém.
            </p>
            <p className="mt-3 text-slate-400">
              Anuncie, combine as datas e receba de volta. Sem intermediário, sem cobrança.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
