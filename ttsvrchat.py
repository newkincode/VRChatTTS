from gtts import gTTS
from pydub import AudioSegment
import tempfile
import os
import requests
import pyaudio
import sounddevice as sd
import numpy as np
import soundfile as sf
from pythonosc import udp_client
import argparse
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import sys
import json
import torch
from TTS.api import TTS


file_json = 0
with open("./setting.json", "r", encoding="UTF-8") as file:
    file_json = json.loads(file.read())

tts = 0
if file_json["my_voice"]:
    # Get device
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # List available 🐸TTS models
    print(TTS().list_models())

    # Init TTS
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)


class RedirectText:
    def __init__(self, text_widget):
        """텍스트 위젯으로 출력을 리디렉션하는 클래스"""
        self.text_widget = text_widget
        self.buffer = ""
        
    def write(self, string):
        """출력을 텍스트 위젯에 작성"""
        self.buffer += string
        self.text_widget.configure(state="normal")
        self.text_widget.insert(tk.END, string)
        self.text_widget.see(tk.END)
        self.text_widget.configure(state="disabled")
        
    def flush(self):
        """버퍼 비우기"""
        self.buffer = ""


class GTTSEngine:


    def __init__(self, tts, device_index=None, language="ko", slow=False, text_cleanup=[["@", ""], ["ㅋ", "크"], ["ㄷ","덜"]], is_my_sound=False):
        self.device_index = device_index
        self.language = language
        self.slow = slow
        self.is_speaking = False
        self.temp_dir = tempfile.gettempdir()
        self.temp_file = os.path.join(self.temp_dir, "gtts_output.wav")
        self.text_cleanup = text_cleanup
        self.is_my_sound = is_my_sound
        self.tts = tts
    
    def auto_text_cleanup(self, text: str, text_auto_cleanup_list):
        for i in text_auto_cleanup_list:
            text = text.replace(i[0], i[1])
        print("클린업 완료: "+text)
        return text

    def speak(self, text):
        """텍스트를 음성으로 변환하고 재생합니다."""
        try:
            # Google TTS로 텍스트를 음성으로 변환
            print("음성 변환 중...")
            cleaned_text = self.auto_text_cleanup(text, self.text_cleanup)
            if cleaned_text:
                if not self.is_my_sound:
                    tts = gTTS(text=cleaned_text, lang=self.language, slow=self.slow)
                    
                    # 임시 파일에 저장
                    tts.save(self.temp_file)
                else:
                    # Text to speech to a file
                    self.tts.tts_to_file(text=cleaned_text, speaker_wav="audio/audio.wav", language="ko", file_path=self.temp_file)
                
                print("재생 준비 중...")
                
                # sounddevice 라이브러리로 재생 시도
                self._play_with_sounddevice()
            else:
                print("텍스트가 비어서 종료")
                
        except Exception as e:
            print(f"음성 변환 중 오류 발생: {e}")
            print("PyAudio로 재생을 시도합니다...")
            self._play_with_pyaudio()

    def stop(self):
        """현재 재생 중인 오디오를 정지합니다."""
        self.is_speaking = False
        try:
            sd.stop()  # sounddevice 사용 시 재생 정지
        except Exception as e:
            print(f"sounddevice 정지 중 오류: {e}")
        # PyAudio 쪽은 재생 루프가 self.is_speaking을 보고 멈추게 되어 있음

    def _play_with_pyaudio(self):
        """PyAudio를 사용하여 음성을 재생합니다."""
        try:
            # 필요한 코드 추가
            print("PyAudio 재생 메서드 호출됨")
        except Exception as e:
            print(f"PyAudio 재생 중 오류: {e}")

    def _play_with_sounddevice(self):
        """sounddevice 라이브러리를 사용하여 오디오를 재생합니다."""
        try:
            # MP3 파일을 numpy 배열로 변환
            audio = AudioSegment.from_mp3(self.temp_file)
            # WAV 파일로 변환
            wav_path = os.path.join(self.temp_dir, "gtts_output.wav")
            audio = audio.set_frame_rate(48000)
            audio.export(wav_path, format="wav")

            # 오디오 파일 로드
            data, samplerate = sf.read(wav_path)
            
            # 지정된 장치로 재생
            print(f"재생 중... (장치 ID: {self.device_index if self.device_index is not None else '기본'})")
            sd.play(data, samplerate=48000, device=self.device_index)
            sd.wait()  # 재생이 끝날 때까지 대기
            print("재생 완료")
            
            # 임시 WAV 파일 제거
            if os.path.exists(wav_path):
                os.remove(wav_path)
                
        except Exception as e:
            print(f"sounddevice 재생 중 오류 발생: {e}")
            print("PyAudio로 대체 재생을 시도합니다...")
            self._play_with_pyaudio()

    def cleanup(self):
        """임시 파일을 정리합니다."""
        try:
            if os.path.exists(self.temp_file):
                os.remove(self.temp_file)
                
            wav_path = os.path.join(self.temp_dir, "gtts_output.wav")
            if os.path.exists(wav_path):
                os.remove(wav_path)
                
            converted_wav = os.path.join(self.temp_dir, "gtts_output_converted.wav")
            if os.path.exists(converted_wav):
                os.remove(converted_wav)
                
        except Exception as e:
            print(f"임시 파일 정리 중 오류 발생: {e}")


def list_audio_devices():
    """사용 가능한 모든 오디오 출력 장치를 나열합니다."""
    try:
        p = pyaudio.PyAudio()
        device_count = p.get_device_count()
        devices = []
        
        for i in range(device_count):
            device_info = p.get_device_info_by_index(i)
            if device_info['maxOutputChannels'] > 0:
                device_name = device_info['name']
                sample_rate = int(device_info.get('defaultSampleRate', 0))
                devices.append((i, device_name, sample_rate))
        
        p.terminate()
        return devices
    except Exception as e:
        print(f"오디오 장치 목록 조회 중 오류 발생: {e}")
        return []


class GTTSApp:
    def __init__(self, root):
        self.file_json = {}
        try:
            with open("./setting.json", "r", encoding="UTF-8") as file:
                self.file_json = json.loads(file.read())
        except Exception as e:
            print(f"설정 파일 로드 실패: {e}")
            # 기본 설정 값 설정
            self.file_json = {
                "is_trans": False,
                "is_say_trans_lang": False,
                "trans_lang": "en",
                "text_auto_cleanup": [["@", ""], ["ㅋ", "크"], ["ㄷ","덜"]]
            }

        self.root = root
        self.root.title("VRChat Tools - Chat Util v1.4.0")
        self.root.geometry("800x600")
        self.root.minsize(200, 200)
        
        # OSC 클라이언트 설정
        parser = argparse.ArgumentParser()
        parser.add_argument("--ip", default="127.0.0.1", help="The ip of the OSC server")
        parser.add_argument("--port", type=int, default=9000, help="The port the OSC server is listening on")
        args = parser.parse_args()
        self.client = udp_client.SimpleUDPClient(args.ip, args.port)
        
        self.tts_engine = None
        
        # 메인 프레임
        self.main_frame = ttk.Frame(root, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.io_frame = ttk.Frame(self.main_frame)

        self.by_text = ttk.Label(text="by Sinoka(sinoka.dev)")
        self.by_text.pack(fill=tk.BOTH, side=tk.TOP)

       # 입력 프레임을 먼저 배치
        self.input_labelframe = ttk.LabelFrame(self.io_frame, text="음성 변환할 텍스트", padding=5)
        self.input_labelframe.pack(fill=tk.BOTH, side=tk.TOP, pady=(0, 5))  # 상단 여백을 0으로 설정

        # 텍스트 입력 영역
        self.input_text = scrolledtext.ScrolledText(self.input_labelframe, wrap=tk.WORD, height=5)
        self.input_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 설정 프레임을 그 다음에 배치
        self.settings_frame = ttk.LabelFrame(self.main_frame, text="설정", padding=10)
        self.settings_frame.pack(fill=tk.X, pady=5)

        # 장치 선택 프레임
        self.device_frame = ttk.Frame(self.settings_frame)
        self.device_frame.pack(fill=tk.X, pady=5)

        
        ttk.Label(self.device_frame, text="오디오 출력 장치:").pack(side=tk.LEFT, padx=5)
        
        # 장치 목록
        self.devices = list_audio_devices()
        self.device_names = ["기본 장치"] + [f"장치 ID {id}: {name} ({rate}Hz)" for id, name, rate in self.devices]
        self.device_var = tk.StringVar(value=self.device_names[0])
        
        self.device_combobox = ttk.Combobox(self.device_frame, textvariable=self.device_var, values=self.device_names, state="readonly", width=50)
        self.device_combobox.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 언어 선택 프레임
        self.language_frame = ttk.Frame(self.settings_frame)
        self.language_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(self.language_frame, text="언어:").pack(side=tk.LEFT, padx=5)
        
        # 언어 목록
        self.languages = {
            "한국어 (ko)": "ko",
            "영어(미국) (en-us)": "en-us",
            "영어(영국) (en-gb)": "en-gb",
            "일본어 (ja)": "ja",
            "중국어 (zh-CN)": "zh-CN",
            "프랑스어 (fr)": "fr",
            "독일어 (de)": "de",
            "스페인어 (es)": "es",
            "이탈리아어 (it)": "it",
            "러시아어 (ru)": "ru"
        }
        self.language_names = list(self.languages.keys())
        self.language_var = tk.StringVar(value=self.language_names[0])
        
        self.language_combobox = ttk.Combobox(self.language_frame, textvariable=self.language_var, values=self.language_names, state="readonly", width=30)
        self.language_combobox.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # 느린 속도 체크박스
        self.slow_var = tk.BooleanVar(value=False)
        self.slow_check = ttk.Checkbutton(self.language_frame, text="느린 속도", variable=self.slow_var)
        self.slow_check.pack(side=tk.LEFT, padx=20)
        
        # 적용 버튼
        self.apply_button = ttk.Button(self.settings_frame, text="설정 적용", command=self.apply_settings)
        self.apply_button.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 중앙 입출력 프레임
        self.io_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 출력 영역 라벨 프레임
        self.output_labelframe = ttk.LabelFrame(self.io_frame, text="출력 로그", padding=5)
        self.output_labelframe.pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM)
        
        # 출력 텍스트 영역
        self.output_text = scrolledtext.ScrolledText(self.output_labelframe, wrap=tk.WORD, height=15)
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.output_text.configure(state="disabled")
        
        # 표준 출력 리디렉션
        self.redirect = RedirectText(self.output_text)
        sys.stdout = self.redirect
        
        # 하단 버튼 프레임
        self.button_frame = ttk.Frame(self.main_frame, padding=5)
        self.button_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        # 실행, 종료, 정지 버튼
        self.play_button = ttk.Button(self.button_frame, text="음성 변환 및 재생", command=self.speak_text, style="Accent.TButton")
        self.play_button.pack(side=tk.RIGHT, padx=5)
        
        self.stop_button = ttk.Button(self.button_frame, text="재생 정지", command=self.stop)
        self.stop_button.pack(side=tk.RIGHT, padx=5)
        
        self.quit_button = ttk.Button(self.button_frame, text="종료", command=self.on_quit)
        self.quit_button.pack(side=tk.RIGHT, padx=5)

        # 엔터 키 바인딩
        self.input_text.bind("<Return>", lambda event: self.speak_text() if not event.state & 0x0001 else None)
        self.input_text.bind("<Shift-Return>", lambda event: None)  # Shift+Enter는 줄바꿈
        
        # 콤보박스 이벤트 바인딩 - 선택 변경 시 바로 설정 적용
        self.device_combobox.bind("<<ComboboxSelected>>", lambda event: self.apply_settings())
        self.language_combobox.bind("<<ComboboxSelected>>", lambda event: self.apply_settings())
        
        # 초기 설정 - 기본값으로 시작
        self.apply_settings()
        
        print("Google TTS를 사용한 음성 출력 프로그램")
        print("※ 이 프로그램은 인터넷 연결이 필요합니다. ※")
        print("=== Google TTS 준비 완료 ===")
            
    def stop(self):
        """현재 재생 중인 음성을 정지합니다."""
        if self.tts_engine:
            self.tts_engine.stop()
            print("음성 재생이 정지되었습니다.")
        
    def apply_settings(self):
        """설정을 적용하고 TTS 엔진을 초기화합니다."""
        try:
            # 장치 ID 가져오기
            device_selection = self.device_var.get()
            device_id = None
            
            if device_selection != "기본 장치":
                # "장치 ID X:" 형식에서 숫자 추출
                try:
                    device_id = int(device_selection.split(":")[0].replace("장치 ID ", "").strip())
                    print(f"장치 ID 선택됨: {device_id}")
                except ValueError as e:
                    print(f"장치 ID 파싱 오류: {e}")
                    device_id = None
            
            # 언어 코드 가져오기
            language_selection = self.language_var.get()
            language_code = None
            
            if self.file_json.get("is_say_trans_lang", False):
                language_code = self.file_json.get("trans_lang", "ko")
                print(f"번역 언어 사용: {language_code}")
            else:
                try:
                    language_code = self.languages[language_selection]
                    print(f"선택된 언어: {language_code}")
                except KeyError:
                    language_code = "ko"  # 기본값
                    print(f"언어 선택 오류. 기본값(ko) 사용")
            
            # 느린 속도 설정
            slow = self.slow_var.get()
            
            # 기존 TTS 엔진이 있으면 정리
            if self.tts_engine:
                self.tts_engine.cleanup()
            
            # 새 엔진 생성
            text_cleanup = self.file_json.get("text_auto_cleanup", [["@", ""], ["ㅋ", "크"], ["ㄷ","덜"]])
            print(self.file_json["my_voice"])
            self.tts_engine = GTTSEngine(tts, device_id, language_code, slow, text_cleanup, self.file_json["my_voice"])
            
            print(f"설정이 적용되었습니다:")
            print(f"- 출력 장치: {device_selection}")
            print(f"- 언어: {language_selection} (코드: {language_code})")
            print(f"- 느린 속도: {'사용' if slow else '사용 안 함'}")
            
        except Exception as e:
            print(f"설정 적용 중 오류 발생: {e}")
            # 오류 발생 시 기본 설정으로 엔진 생성
            self.tts_engine = GTTSEngine()

    def speak_text(self):
        """입력된 텍스트를 음성으로 변환합니다."""
        text = self.input_text.get("1.0", tk.END).strip()
        if text:
            print(f"입력된 텍스트: {text}")
            # 번역
            translated_text = text
            if self.file_json.get("is_trans", False):
                translated_text = self.trans(text)
                print(f"번역된 텍스트: {translated_text}")
            
            # OSC 메시지 전송
            try:
                if self.file_json.get("is_trans", False):
                    self.client.send_message("/chatbox/input", (text + "\n" + translated_text, True, True))
                else:
                    self.client.send_message("/chatbox/input", (text, True, True))
                print("OSC 메시지 전송 완료")
            except Exception as e:
                print(f"OSC 메시지 전송 중 오류: {e}")
            
            # 백그라운드 스레드에서 음성 변환 및 재생
            try:
                if self.file_json.get("is_say_trans_lang", False) and self.file_json.get("is_trans", False):
                    threading.Thread(target=self.tts_engine.speak, args=(translated_text,), daemon=True).start()
                else:
                    threading.Thread(target=self.tts_engine.speak, args=(text,), daemon=True).start()
            except Exception as e:
                print(f"음성 재생 스레드 시작 중 오류: {e}")
        else:
            print("텍스트가 비어있습니다.")

    def trans(self, text: str):
        """텍스트를 번역하고 번역 결과를 반환합니다."""
        try:
            trans_lang = self.file_json.get("trans_lang", "en")
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={trans_lang}&dt=t&q={text.replace(' ', '+')}"
            response = requests.get(url)
            response.raise_for_status()  # HTTP 오류 확인
            data = response.json()
            translated_text = data[0][0][0]
            return translated_text
        except Exception as e:
            print(f"번역 중 오류 발생: {e}")
            return text  # 오류 발생 시 원본 텍스트 반환

    def on_quit(self):
        """프로그램 종료"""
        if self.tts_engine:
            self.tts_engine.cleanup()
        self.root.destroy()


def main():
    # Tkinter 테마 설정 (Windows에서만 작동)
    try:
        if os.name == 'nt':  # Windows
            from ctypes import windll
            try:
                windll.shcore.SetProcessDpiAwareness(1)  # DPI 인식 설정
            except Exception as e:
                print(f"DPI 설정 오류: {e}")
            
            # 시스템 테마 감지 시도
            try:
                import winreg
                registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
                theme_value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                is_dark_mode = theme_value == 0
            except Exception as e:
                print(f"테마 감지 오류: {e}")
                is_dark_mode = False
            
            # 다크 모드이면 스타일 추가
            root = tk.Tk()
            if is_dark_mode:
                try:
                    # Windows 11/10에서 다크 모드 스타일 적용
                    style = ttk.Style(root)
                    root.tk.call("source", "sun-valley.tcl")
                    root.tk.call("set_theme", "dark")
                except Exception as e:
                    print(f"다크 테마 적용 오류: {e}")
            else:
                # 기본 테마 사용
                pass
        else:
            # 다른 OS에서는 기본 테마
            root = tk.Tk()
    except Exception as e:
        print(f"테마 설정 중 오류: {e}")
        # 오류 발생 시 기본 설정
        root = tk.Tk()
    
    # 스타일 설정
    style = ttk.Style()
    if 'Accent.TButton' not in style.map('TButton'):
        # 특별 스타일 추가
        style.configure('Accent.TButton', background='#007bff', foreground='white')
        style.map('Accent.TButton',
                  background=[('active', '#0069d9'), ('pressed', '#0062cc')],
                  foreground=[('active', 'white'), ('pressed', 'white')])
    
    app = GTTSApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()