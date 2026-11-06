/** Barra de progrés amb el valor i el total sempre escrits. */
export function Mesurador({ valor, total, etiqueta }: { valor: number; total: number; etiqueta: string }) {
  const f = total > 0 ? Math.min(1, valor / total) : 0;
  return (
    <div className="mesurador" role="progressbar" aria-label={etiqueta} aria-valuemin={0} aria-valuemax={total} aria-valuenow={Math.min(valor, total)}>
      <span style={{ width: `${f * 100}%` }} />
    </div>
  );
}
