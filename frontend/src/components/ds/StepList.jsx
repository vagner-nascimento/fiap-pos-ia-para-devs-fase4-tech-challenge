/**
 * StepList — Lista vertical de etapas com marcadores circulares.
 * Conforme Mock 4 (Processamento):
 * ✓ verde para concluída, … teal para ativa, número cinza para pendente.
 */
export function StepList({ steps = [], currentStepIndex = 0 }) {
  return (
    <div className="step-list" role="list">
      {steps.map((step, idx) => {
        let status = step.status;
        if (!status) {
          if (idx < currentStepIndex) status = 'completed';
          else if (idx === currentStepIndex) status = 'active';
          else status = 'pending';
        }

        return (
          <div key={idx} className="st" role="listitem">
            {status === 'completed' && (
              <span className="dot dot-completed" aria-label="Etapa concluída">✓</span>
            )}
            {status === 'active' && (
              <span className="dot dot-active" aria-label="Etapa em processamento">…</span>
            )}
            {status === 'error' && (
              <span className="dot dot-error" aria-label="Etapa com erro">✕</span>
            )}
            {status === 'pending' && (
              <span className="dot dot-pending" aria-label={`Etapa ${idx + 1}`}>{idx + 1}</span>
            )}
            <div className="st-info">
              <span className={`st-label ${status === 'active' ? 'st-active-label' : ''}`}>
                {step.title}
              </span>
              {step.description && <p className="mu st-desc">{step.description}</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
