export function Card({ className = '', style = {}, children, ...props }) {
  return (
    <div className={`c ${className}`.trim()} style={style} {...props}>
      {children}
    </div>
  );
}
