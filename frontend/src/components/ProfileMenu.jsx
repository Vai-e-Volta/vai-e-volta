import { useEffect, useId, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '../hooks/useAuth';

const itemClassName =
  'block w-full rounded-md px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/5 hover:text-white focus:bg-white/10 focus:text-white focus:outline-none';

/**
 * Ícone de perfil com menu suspenso Perfil, Configurações e Sair (F-09), no padrão
 * WAI-ARIA de botão de menu: Enter, Espaço ou seta abrem; setas, Home e End navegam;
 * Esc fecha e devolve o foco ao botão.
 */
export default function ProfileMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [isLeaving, setIsLeaving] = useState(false);
  const containerRef = useRef(null);
  const buttonRef = useRef(null);
  const itemRefs = useRef([]);
  const focusOnOpen = useRef(0);
  const menuId = useId();
  const username = user?.username ?? '';

  const items = [
    {
      id: 'profile',
      label: 'Perfil',
      action: () => navigate(`/usuarios/${encodeURIComponent(username)}`),
    },
    { id: 'settings', label: 'Configurações', action: () => navigate('/configuracoes') },
    { id: 'listings', label: 'Meus anúncios', action: () => navigate('/alugueis?visao=anuncios') },
    {
      id: 'logout',
      label: isLeaving ? 'Saindo…' : 'Sair',
      // Sem sessão, a rota privada leva ao /login.
      action: async () => {
        setIsLeaving(true);
        await logout();
      },
    },
  ];

  useEffect(() => {
    if (!open) return undefined;
    itemRefs.current[focusOnOpen.current]?.focus();

    function handlePointerDown(event) {
      if (!containerRef.current?.contains(event.target)) setOpen(false);
    }
    document.addEventListener('pointerdown', handlePointerDown);
    return () => document.removeEventListener('pointerdown', handlePointerDown);
  }, [open]);

  function openMenu(index) {
    focusOnOpen.current = index;
    setOpen(true);
  }

  function closeMenu({ returnFocus = true } = {}) {
    setOpen(false);
    if (returnFocus) buttonRef.current?.focus();
  }

  function handleButtonKeyDown(event) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      openMenu(0);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      openMenu(items.length - 1);
    }
  }

  function handleMenuKeyDown(event) {
    const current = itemRefs.current.indexOf(document.activeElement);
    const last = items.length - 1;
    const moves = {
      ArrowDown: current >= last ? 0 : current + 1,
      ArrowUp: current <= 0 ? last : current - 1,
      Home: 0,
      End: last,
    };
    if (event.key in moves) {
      event.preventDefault();
      itemRefs.current[moves[event.key]]?.focus();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      closeMenu();
    } else if (event.key === 'Tab') {
      closeMenu({ returnFocus: false });
    }
  }

  function handleSelect(item) {
    closeMenu({ returnFocus: item.id !== 'logout' });
    item.action();
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={`Menu da conta de ${username}`}
        onClick={() => (open ? closeMenu() : openMenu(0))}
        onKeyDown={handleButtonKeyDown}
        disabled={isLeaving}
        className="flex h-10 w-10 items-center justify-center rounded-full border border-line bg-panel text-sm font-semibold uppercase text-accent transition-colors hover:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-60"
      >
        <span aria-hidden="true">{username.charAt(0) || '?'}</span>
      </button>

      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label="Conta"
          onKeyDown={handleMenuKeyDown}
          className="absolute right-0 z-40 mt-2 w-52 rounded-xl border border-line bg-surface p-1.5 shadow-xl shadow-black/30"
        >
          <p className="truncate px-3 pb-2 pt-1.5 text-xs text-slate-400" aria-hidden="true">
            @{username}
          </p>
          {items.map((item, index) => (
            <button
              key={item.id}
              ref={(element) => {
                itemRefs.current[index] = element;
              }}
              type="button"
              role="menuitem"
              tabIndex={-1}
              onClick={() => handleSelect(item)}
              className={itemClassName}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
