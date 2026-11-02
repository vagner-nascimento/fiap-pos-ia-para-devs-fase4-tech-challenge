export function Button({ variant = 'primary', className = '', children, ...props }) {
  const variantClass = variant === 'secondary' ? 'btn s' : 'btn';
  return (
    <button className={`${variantClass} ${className}`.trim()} {...props}>
      {children}
    </button>
  );
}
