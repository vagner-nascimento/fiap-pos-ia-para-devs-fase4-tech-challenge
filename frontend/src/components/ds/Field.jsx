/**
 * Field — Componente de formulário do Design System (docs/design/DESIGN.md seção 2).
 * Renderiza <label> 13px/700 acima do controle (.in) com altura mínima de 44px
 * (ou 96px quando multiline=true).
 */
export function Field({
  id,
  label,
  multiline = false,
  children,
  hint,
  style = {},
  ...inputProps
}) {
  return (
    <div className="ds-field" style={style}>
      {label && <label htmlFor={id}>{label}</label>}
      {children ? (
        children
      ) : multiline ? (
        <textarea id={id} className="in ds-textarea" {...inputProps} />
      ) : (
        <input id={id} className="in" {...inputProps} />
      )}
      {hint && (
        <p className="mu" style={{ marginTop: '4px', fontSize: '12px' }}>
          {hint}
        </p>
      )}
    </div>
  );
}

