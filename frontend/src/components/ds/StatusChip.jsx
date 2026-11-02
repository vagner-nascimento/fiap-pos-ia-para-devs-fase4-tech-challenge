/**
 * StatusChip — Pílula de status clínico.
 * Conforme Princípio 4 do Design System do Fisio Coach:
 * "Estado nunca só por cor: chip = símbolo + texto + cor (● Verde, ▲ Atenção, ■ Crítico)"
 */
export function StatusChip({ level = 'ok', label, symbol, className = '', style = {}, ...props }) {
  const defaultSymbols = {
    ok: '●',
    warn: '▲',
    crit: '■',
    info: 'ℹ',
  };

  const sym = symbol !== undefined ? symbol : (defaultSymbols[level] || '●');
  const levelClass = {
    ok: 'ok',
    warn: 'wa',
    crit: 'cr',
    info: 'ne',
  }[level] || 'ne';

  return (
    <span className={`ch ${levelClass} ${className}`.trim()} style={style} {...props}>
      {sym && <span className="ch-sym" aria-hidden="true">{sym}</span>}
      <span>{label}</span>
    </span>
  );
}
