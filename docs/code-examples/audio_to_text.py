import moviepy.editor as mp
import speech_recognition as sr
import os

def extract_audio_from_video(video_path, audio_path):
    video = mp.VideoFileClip(video_path)
    video.audio.write_audiofile(audio_path, verbose=False, logger=None)

def transcribe_audio_to_text(audio_path, text_output_path):
    '''
    IMPORTANTE: Somente a API da Google não pede credenciais de API, a demais pedem.
    Para mais informações, consulte a documentação oficial do SpeechRecognition.
    NOTA: Copiei os videos desejados do repositorio de datasets para a pasta videos 
        e altere os nomes dos arquivos de vídeo e áudio para que o código funcione corretamente.
    '''
    recognizer = sr.Recognizer()
    
    with sr.AudioFile(audio_path) as source:
        audio = recognizer.record(source)  # lê todo o áudio do arquivo
        try:
            # Usa o serviço de reconhecimento de fala do Google
            print(f"Tentando o Google Speech Recognition para {os.path.basename(audio_path)}")
            text = recognizer.recognize_google(audio, language="pt-BR")  # Use "en-US" para inglês
            print("Transcrição: " + text)
            
            # Salva a transcrição em um arquivo de texto
            with open(text_output_path, 'w', encoding='utf-8') as file:
                file.write(text)
                
        except sr.UnknownValueError:
            print("Google Speech Recognition não conseguiu entender o áudio")
        except sr.RequestError as e:
            print("Erro ao solicitar resultados do serviço de reconhecimento de fala do Google; {0}".format(e))

# Definindo os caminhos dos arquivos de vídeo, áudio e texto
script_dir = os.path.dirname(os.path.abspath(__file__))
PATH_VIDEOS = os.path.join(script_dir, "videos/")
PATH_AUDIOS = os.path.join(script_dir, "audios/")
PATH_TEXT = os.path.join(script_dir, "texts/")

# Definindo os caminhos dos arquivos de vídeo cada vídeo FISIO-006
PATH_VIDEO_FISIO_006_C1 = os.path.join(PATH_VIDEOS, "FISIO-006-C01.mp4")
PATH_VIDEO_FISIO_006_C2 = os.path.join(PATH_VIDEOS, "FISIO-006-C02.mp4")
PATH_VIDEO_FISIO_006_C3 = os.path.join(PATH_VIDEOS, "FISIO-006-C03.mp4")
PATH_VIDEO_FISIO_006_C4 = os.path.join(PATH_VIDEOS, "FISIO-006-C04.mp4")

# Definindo os caminhos dos arquivos de áudio cada vídeo FISIO-006
PATH_AUDIO_FISIO_006_C1 = os.path.join(PATH_AUDIOS, "FISIO-006-C01.wav")
PATH_AUDIO_FISIO_006_C2 = os.path.join(PATH_AUDIOS, "FISIO-006-C02.wav")
PATH_AUDIO_FISIO_006_C3 = os.path.join(PATH_AUDIOS, "FISIO-006-C03.wav")
PATH_AUDIO_FISIO_006_C4 = os.path.join(PATH_AUDIOS, "FISIO-006-C04.wav")

# Definindo os caminhos dos arquivos de texto cada audio FISIO-006
PATH_TEXT_FISIO_006_C1 = os.path.join(PATH_TEXT, "FISIO-006-C01.txt")
PATH_TEXT_FISIO_006_C2 = os.path.join(PATH_TEXT, "FISIO-006-C02.txt")
PATH_TEXT_FISIO_006_C3 = os.path.join(PATH_TEXT, "FISIO-006-C03.txt")
PATH_TEXT_FISIO_006_C4 = os.path.join(PATH_TEXT, "FISIO-006-C04.txt")

# Definindo os caminhos dos arquivos de vídeo cada vídeo FISIO-007
PATH_VIDEO_FISIO_007_C1 = os.path.join(PATH_VIDEOS, "FISIO-007-C01.mp4")
PATH_VIDEO_FISIO_007_C2 = os.path.join(PATH_VIDEOS, "FISIO-007-C02.mp4")
PATH_VIDEO_FISIO_007_C3 = os.path.join(PATH_VIDEOS, "FISIO-007-C03.mp4")
PATH_VIDEO_FISIO_007_C4 = os.path.join(PATH_VIDEOS, "FISIO-007-C04.mp4")

# Definindo os caminhos dos arquivos de áudio cada vídeo FISIO-007
PATH_AUDIO_FISIO_007_C1 = os.path.join(PATH_AUDIOS, "FISIO-007-C01.wav")
PATH_AUDIO_FISIO_007_C2 = os.path.join(PATH_AUDIOS, "FISIO-007-C02.wav")
PATH_AUDIO_FISIO_007_C3 = os.path.join(PATH_AUDIOS, "FISIO-007-C03.wav")
PATH_AUDIO_FISIO_007_C4 = os.path.join(PATH_AUDIOS, "FISIO-007-C04.wav")

# Definindo os caminhos dos arquivos de texto cada audio FISIO-007
PATH_TEXT_FISIO_007_C1 = os.path.join(PATH_TEXT, "FISIO-007-C01.txt")
PATH_TEXT_FISIO_007_C2 = os.path.join(PATH_TEXT, "FISIO-007-C02.txt")
PATH_TEXT_FISIO_007_C3 = os.path.join(PATH_TEXT, "FISIO-007-C03.txt")
PATH_TEXT_FISIO_007_C4 = os.path.join(PATH_TEXT, "FISIO-007-C04.txt")

def execute_fisio_006():
    extract_audio_from_video(PATH_VIDEO_FISIO_006_C1, PATH_AUDIO_FISIO_006_C1)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_006_C1, PATH_TEXT_FISIO_006_C1)

    extract_audio_from_video(PATH_VIDEO_FISIO_006_C2, PATH_AUDIO_FISIO_006_C2)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_006_C2, PATH_TEXT_FISIO_006_C2)

    extract_audio_from_video(PATH_VIDEO_FISIO_006_C3, PATH_AUDIO_FISIO_006_C3)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_006_C3, PATH_TEXT_FISIO_006_C3)

    extract_audio_from_video(PATH_VIDEO_FISIO_006_C4, PATH_AUDIO_FISIO_006_C4)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_006_C4, PATH_TEXT_FISIO_006_C4)

def execute_fisio_007():
    extract_audio_from_video(PATH_VIDEO_FISIO_007_C1, PATH_AUDIO_FISIO_007_C1)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_007_C1, PATH_TEXT_FISIO_007_C1)

    extract_audio_from_video(PATH_VIDEO_FISIO_007_C2, PATH_AUDIO_FISIO_007_C2)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_007_C2, PATH_TEXT_FISIO_007_C2)

    extract_audio_from_video(PATH_VIDEO_FISIO_007_C3, PATH_AUDIO_FISIO_007_C3)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_007_C3, PATH_TEXT_FISIO_007_C3)

    extract_audio_from_video(PATH_VIDEO_FISIO_007_C4, PATH_AUDIO_FISIO_007_C4)
    transcribe_audio_to_text(PATH_AUDIO_FISIO_007_C4, PATH_TEXT_FISIO_007_C4)

if __name__ == "__main__":
   execute_fisio_006()
   execute_fisio_007()
