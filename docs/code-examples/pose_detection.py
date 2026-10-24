## Código de exemplo para geração da  avaliação dos vídeos, usando os landmarks do mediapipe.

from ast import Tuple
import cv2
import mediapipe as mp
import os
from tqdm import tqdm


def is_arm_up(landmarks, mp_pose):
    right_eye = landmarks[mp_pose.PoseLandmark.RIGHT_EYE.value]
    left_eye = landmarks[mp_pose.PoseLandmark.LEFT_EYE.value]
    right_elbow = landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value]
    left_elbow = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value]

    left_arm_up = left_elbow.y < left_eye.y
    right_arm_up = right_elbow.y < right_eye.y

    return left_arm_up or right_arm_up

def is_ankle_up(landmarks, mp_pose):
    right_ankle = landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value]
    right_knee = landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value]
    right_elbow = landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value]
    left_elbow = landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value]

    right_ankle_up = right_ankle.y <= right_knee.y
    right_ankle_moved = right_ankle.x > right_knee.y

    return (right_ankle_moved,right_ankle_up)



def detect_pose(video_path=None, output_path=None):

    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose()
    mp_drawing = mp.solutions.drawing_utils


    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print(f'Erro ao abrir camera')
        return

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    # total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        results = pose.process(rgb_frame)

        if results.pose_landmarks:
            mp_drawing.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            if is_arm_up(results.pose_landmarks.landmark, mp_pose):
                cv2.putText(frame, "braço levantado", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1, cv2.LINE_AA)

        cv2.imshow("Poses",frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

def detect_pose_from_video(video_path=None, output_path=None):

    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose()
    mp_drawing = mp.solutions.drawing_utils

    if not os.path.exists(video_path):
        print(f'Vídeo {video_path} não encontrado!')
        return

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f'Erro ao abrir camera')
        return

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (w,h))


    for _ in tqdm(range(total_frames), desc="Processando vídeo"):
        ret, frame = cap.read()

        if not ret:
            break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        results = pose.process(rgb_frame)

        if results.pose_landmarks:
            mp_drawing.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            ankle_up, ankle_moved = is_ankle_up(results.pose_landmarks.landmark, mp_pose)
            if ankle_moved:
                cv2.putText(frame, "Movimento iniciado", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1, cv2.LINE_AA)
            else:
                cv2.putText(frame, "Parado", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1, cv2.LINE_AA)
        
            if ankle_up:
                cv2.putText(frame, "Movimento completo", (10,50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1, cv2.LINE_AA)
            else:
                cv2.putText(frame, "Movimento incompleto", (10,50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,0), 1, cv2.LINE_AA)
        
        out.write(frame)


    cap.release()
    out.release()
    cv2.destroyAllWindows()

script_dir = os.path.dirname(os.path.abspath(__file__))
input_video_path = os.path.join(script_dir, 'videos','FISIO-001-correto.mp4')
output_video_path = os.path.join(script_dir, 'videos','video_out.mp4')


type = int(input("tipo de analise (1: camera / 2:video)"))

if type == 1:
    detect_pose()

if type == 2:
    detect_pose_from_video(input_video_path,output_video_path)
    