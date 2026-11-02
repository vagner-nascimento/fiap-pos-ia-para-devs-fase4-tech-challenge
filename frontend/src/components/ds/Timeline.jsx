/**
 * Timeline — Faixas temporais alinhadas para biomecânica e eventos de dor.
 * Conforme Design System:
 * Faixas de 28px (--fc-track-bg), blocos de 20px com raio 4px.
 * Uma faixa por tipo: Repetições (--fc-track-rep), Desvios (--fc-track-desvio), Dor facial (--fc-track-dor), Fala (--fc-track-fala).
 */
export function Timeline({
  events = [],
  duration = 0,
  currentTime = 0,
  onSeek = () => {},
}) {
  const safeDuration = duration > 0 ? duration : 1;

  // Separa eventos por tipo de faixa
  const repetitions = events.filter((e) => e.tipo === 'repeticao');
  const deviations = events.filter((e) => e.tipo === 'desvio');
  const facePain = events.filter((e) => e.tipo === 'dor_facial');
  const speechPain = events.filter((e) => e.tipo === 'fala_dor');

  const getPositionPercent = (time) => {
    const clamped = Math.max(0, Math.min(time || 0, safeDuration));
    return (clamped / safeDuration) * 100;
  };

  const getWidthPercent = (start, end) => {
    const s = Math.max(0, start || 0);
    const e = Math.min(safeDuration, end || start + 0.5);
    const w = ((e - s) / safeDuration) * 100;
    return Math.max(w, 2.5); // Garante visibilidade mínima de clique
  };

  const handleTrackClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(clickX / rect.width, 1));
    onSeek(ratio * safeDuration);
  };

  const currentPercent = getPositionPercent(currentTime);

  return (
    <div className="timeline-container">
      {/* Indicador de cursor comum */}
      <div className="timeline-header-meta">
        <span className="mu">Linha do tempo biomecânica</span>
        <span className="mu">{currentTime.toFixed(1)}s / {safeDuration.toFixed(1)}s</span>
      </div>

      <div className="timeline-tracks-wrapper" onClick={handleTrackClick}>
        {/* Cursor vertical de tempo comum sincronizado com o player */}
        <div
          className="timeline-playhead"
          style={{ left: `${currentPercent}%` }}
          aria-hidden="true"
        />

        {/* Faixa 1: Repetições */}
        <div className="timeline-track-row">
          <span className="timeline-track-label">Repetições</span>
          <div className="trk" title="Clique para navegar no vídeo">
            {repetitions.map((rep, idx) => {
              const left = getPositionPercent(rep.instante_inicio);
              const width = getWidthPercent(rep.instante_inicio, rep.instante_fim);
              const isInvalid = rep.valores?.is_valid === false;
              return (
                <button
                  key={idx}
                  type="button"
                  className="trk-block trk-rep"
                  style={{
                    left: `${left}%`,
                    width: `${width}%`,
                    background: isInvalid ? 'var(--fc-warn-fg)' : 'var(--fc-track-rep)',
                  }}
                  onClick={(ev) => {
                    ev.stopPropagation();
                    onSeek(rep.instante_inicio);
                  }}
                  title={`Repetição #${rep.valores?.index || idx + 1} (${isInvalid ? 'com desvio' : 'válida'}) - Início: ${rep.instante_inicio.toFixed(1)}s`}
                >
                  <span className="trk-text">{rep.valores?.index || idx + 1}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Faixa 2: Desvios de Postura */}
        <div className="timeline-track-row">
          <span className="timeline-track-label">Desvios de postura</span>
          <div className="trk">
            {deviations.length === 0 ? (
              <span className="trk-empty">Nenhum desvio registrado</span>
            ) : (
              deviations.map((dev, idx) => {
                const left = getPositionPercent(dev.instante_inicio);
                const width = getWidthPercent(dev.instante_inicio, dev.instante_fim);
                return (
                  <button
                    key={idx}
                    type="button"
                    className="trk-block trk-desvio"
                    style={{
                      left: `${left}%`,
                      width: `${width}%`,
                      background: 'var(--fc-track-desvio)',
                    }}
                    onClick={(ev) => {
                      ev.stopPropagation();
                      onSeek(dev.instante_inicio);
                    }}
                    title={`Desvio: ${dev.descricao || 'Desvio postural'} - Início: ${dev.instante_inicio.toFixed(1)}s`}
                  />
                );
              })
            )}
          </div>
        </div>

        {/* Faixa 3: Dor Facial (RF-07: sem dado não é sem dor) */}
        <div className="timeline-track-row">
          <span className="timeline-track-label">Dor facial</span>
          <div className="trk">
            {facePain.length === 0 ? (
              <span className="trk-empty trk-striped">sem dado registrado</span>
            ) : (
              facePain.map((pain, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="trk-block trk-dor"
                  style={{
                    left: `${getPositionPercent(pain.instante_inicio)}%`,
                    width: `${getWidthPercent(pain.instante_inicio, pain.instante_fim)}%`,
                    background: 'var(--fc-track-dor)',
                  }}
                  onClick={(ev) => {
                    ev.stopPropagation();
                    onSeek(pain.instante_inicio);
                  }}
                  title={`Dor facial: ${pain.descricao || 'Expressão de desconforto'}`}
                />
              ))
            )}
          </div>
        </div>

        {/* Faixa 4: Fala de Dor */}
        <div className="timeline-track-row">
          <span className="timeline-track-label">Fala de dor</span>
          <div className="trk">
            {speechPain.length === 0 ? (
              <span className="trk-empty">Nenhuma queixa de dor verbalizada</span>
            ) : (
              speechPain.map((speech, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="trk-block trk-fala"
                  style={{
                    left: `${getPositionPercent(speech.instante_inicio)}%`,
                    width: `${getWidthPercent(speech.instante_inicio, speech.instante_fim)}%`,
                    background: 'var(--fc-track-fala)',
                  }}
                  onClick={(ev) => {
                    ev.stopPropagation();
                    onSeek(speech.instante_inicio);
                  }}
                  title={`Fala: "${speech.descricao || 'Queixa verbal'}"`}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
