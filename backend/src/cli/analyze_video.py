import argparse
import sys
import time
from pathlib import Path

# Garante que `backend/src` esteja no sys.path mesmo ao executar o script diretamente
_SRC_DIR = Path(__file__).resolve().parents[1]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from config.media_paths import MediaStorage
from services.pose.registry import supported_exercises
from services.pose.video_processor import VideoPoseProcessor


def main():
    parser = argparse.ArgumentParser(
        description="Fisio Coach — Análise de Movimento e Postura em Vídeo via MediaPipe Pose"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--video", type=str, help="Caminho direto para o arquivo de vídeo .mp4")
    group.add_argument(
        "--dataset-clip",
        type=str,
        help="Nome do clipe dentro de DATASET_ROOT (requer --case, ex: FISIO-001-correto.mp4)",
    )

    parser.add_argument(
        "--case",
        type=str,
        required=True,
        help=f"Identificador do exercício (ex: FISIO-001). Disponíveis: {', '.join(supported_exercises())}",
    )
    parser.add_argument(
        "--side",
        type=str,
        default="auto",
        help="Lado do exercício: 'direito', 'esquerdo' ou 'auto' (padrão: auto)",
    )
    parser.add_argument(
        "--target-reps",
        type=int,
        default=5,
        help="Número de repetições prescritas / alvo (padrão: 5)",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Identificador da execução/sessão (padrão: gerado a partir do caso e timestamp)",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="Desativa a geração do vídeo MP4 anotado (processamento mais rápido)",
    )

    args = parser.parse_args()
    storage = MediaStorage.from_env()

    if args.dataset_clip:
        video_path = storage.dataset_clip(args.case, args.dataset_clip)
    else:
        video_path = Path(args.video).resolve()

    if not video_path.exists():
        print(f"Erro: vídeo não encontrado em '{video_path}'", file=sys.stderr)
        sys.exit(1)

    run_id = args.run_id or f"{args.case}_{int(time.time())}"

    print(f"\n=======================================================")
    print(f" Iniciando Análise de Postura com MediaPipe")
    print(f" Vídeo de entrada: {video_path}")
    print(f" Exercício:        {args.case.upper()}")
    print(f" Lado:             {args.side}")
    print(f" Repetições alvo:  {args.target_reps}")
    print(f" ID de Execução:   {run_id}")
    print(f"=======================================================\n")

    processor = VideoPoseProcessor(media_storage=storage)

    def progress_callback(stage: str, pct: float):
        print(f"[{pct*100:5.1f}%] {stage}...")

    t0 = time.time()
    result = processor.process_video(
        video_path=video_path,
        exercise_identifier=args.case,
        run_id=run_id,
        side=args.side,
        target_repetitions=args.target_reps,
        generate_annotated_video=not args.no_render,
        on_progress=progress_callback,
    )
    elapsed = time.time() - t0

    s = result.session_summary
    print(f"\n=======================================================")
    print(f" Análise Concluída com Sucesso em {elapsed:.1f}s!")
    print(f"=======================================================")
    print(f" Lado avaliado:           {s.side_evaluated}")
    print(f" Repetições concluídas:   {s.completed_repetitions} de {s.target_repetitions}")
    print(f" Repetições válidas:      {s.valid_repetitions}")
    print(f" Score de conformidade:   {s.compliance_score:.1f}%")
    print(f" Desvios detectados:      {len(result.deviations)}")

    if result.deviations:
        print("\n Desvios identificados:")
        for dev in result.deviations:
            print(f"  - [Rep {dev.repetition_index or '-'}] {dev.deviation_type} ({dev.severity.value}): {dev.description}")

    if s.limitations:
        print("\n Observações/Limitações:")
        for lim in s.limitations:
            print(f"  * {lim}")

    out_dir = storage.pose_output_dir(run_id)
    print(f"\n Artefatos gerados em:")
    print(f"  Pasta:           {out_dir}")
    print(f"  Resumo JSON:     {storage.analysis_json(run_id)}")
    print(f"  Telemetria JSON: {storage.telemetry_json(run_id)}")
    if result.annotated_video_path:
        print(f"  Vídeo Anotado:   {storage.annotated_video(run_id)}")
    print(f"=======================================================\n")


if __name__ == "__main__":
    main()
