import { useRef, useEffect, useState } from 'react';
import { Play, Pause, RotateCcw, Volume2, VolumeX, Maximize } from 'lucide-react';

/**
 * VideoPlayer — Player de vídeo responsivo com HUD anotado integrado e suporte a busca temporal.
 */
export function VideoPlayer({
  src,
  onTimeUpdate,
  onLoadedMetadata,
  seekTime = null,
  className = '',
}) {
  const videoRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [hasError, setHasError] = useState(false);

  // Reage a saltos temporais solicitados pela timeline ou cliques em eventos
  useEffect(() => {
    if (seekTime !== null && videoRef.current && Number.isFinite(seekTime)) {
      videoRef.current.currentTime = seekTime;
      setCurrentTime(seekTime);
    }
  }, [seekTime]);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const cur = videoRef.current.currentTime;
      setCurrentTime(cur);
      if (onTimeUpdate) {
        onTimeUpdate(cur);
      }
    }
  };

  const handleLoaded = () => {
    if (videoRef.current) {
      const dur = videoRef.current.duration || 0;
      setDuration(dur);
      setHasError(false);
      if (onLoadedMetadata) {
        onLoadedMetadata(dur);
      }
    }
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      videoRef.current.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
    }
  };

  const toggleMute = () => {
    if (!videoRef.current) return;
    videoRef.current.muted = !isMuted;
    setIsMuted(!isMuted);
  };

  const restart = () => {
    if (!videoRef.current) return;
    videoRef.current.currentTime = 0;
    videoRef.current.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
  };

  const toggleFullscreen = () => {
    if (videoRef.current && videoRef.current.requestFullscreen) {
      videoRef.current.requestFullscreen();
    }
  };

  const formatTime = (seconds) => {
    if (!seconds || !Number.isFinite(seconds)) return '00:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className={`video-player-container ${className}`.trim()}>
      <div className="video-viewport">
        {hasError ? (
          <div className="video-error-state">
            <p>Não foi possível carregar o vídeo anotado.</p>
            <small className="mu">Verifique se o backend está servindo /media</small>
          </div>
        ) : (
          <video
            ref={videoRef}
            src={src}
            playsInline
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoaded}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            onError={() => setHasError(true)}
            className="video-element"
          />
        )}
      </div>

      <div className="video-controls-bar">
        <div className="controls-left">
          <button
            type="button"
            className="control-btn"
            onClick={togglePlay}
            aria-label={isPlaying ? 'Pausar vídeo' : 'Reproduzir vídeo'}
          >
            {isPlaying ? <Pause size={17} /> : <Play size={17} />}
          </button>
          <button
            type="button"
            className="control-btn"
            onClick={restart}
            aria-label="Reiniciar vídeo"
          >
            <RotateCcw size={16} />
          </button>
          <button
            type="button"
            className="control-btn"
            onClick={toggleMute}
            aria-label={isMuted ? 'Ativar áudio' : 'Desativar áudio'}
          >
            {isMuted ? <VolumeX size={17} /> : <Volume2 size={17} />}
          </button>
          <span className="video-timer">
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>
        </div>

        <div className="controls-right">
          <button
            type="button"
            className="control-btn"
            onClick={toggleFullscreen}
            aria-label="Tela cheia"
          >
            <Maximize size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
