"""L4-3 実践: 音声パイプライン（STT → LLM → TTS）。

 ① STT: 音声ファイル（input.wav）を Azure Speech でテキスト化
 ② LLM: Responses API でテキストを処理
 ③ TTS: 応答テキストを Azure Speech で音声化（output.wav）
キーレス認証（Entra ID）。STT も TTS も SpeechConfig(token_credential=..., endpoint=カスタムドメイン)。

使い方:
  python main.py make-input "質問の文"   # TTS で質問の音声 input.wav を作る（マイクの無い環境向け）
  python main.py                         # input.wav → STT → LLM → TTS → output.wav
  python main.py stt output.wav          # 任意の wav を STT だけにかける（出力の確かめ）
"""

import os
import sys
import wave
import azure.cognitiveservices.speech as speechsdk
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from dotenv import load_dotenv

load_dotenv()

SPEECH_ENDPOINT = os.getenv("SPEECH_ENDPOINT")
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-5.4")
INPUT_WAV = os.getenv("INPUT_WAV", "input.wav")
TTS_VOICE = os.getenv("TTS_VOICE", "ja-JP-NanamiNeural")

credential = DefaultAzureCredential()


def speech_config() -> speechsdk.SpeechConfig:
    """STT と TTS で共通の設定（キーレス：token_credential ＋ カスタムドメインの endpoint）。"""
    return speechsdk.SpeechConfig(token_credential=credential, endpoint=SPEECH_ENDPOINT)


def wav_info(path: str) -> str:
    """wav の長さとサイズ（動画では音が聞こえないので、数字で確かめる）。"""
    with wave.open(path, "rb") as w:
        sec = w.getnframes() / w.getframerate()
        rate = w.getframerate()
    return f"{sec:.1f} 秒・{rate} Hz・{os.path.getsize(path):,} バイト"


def speech_to_text(path: str) -> str:
    """① STT：音声ファイルをテキスト化。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} が見つかりません（先に make-input で作る）")
    cfg = speech_config()
    cfg.speech_recognition_language = "ja-JP"
    audio_config = speechsdk.audio.AudioConfig(filename=path)
    recognizer = speechsdk.SpeechRecognizer(speech_config=cfg, audio_config=audio_config)
    result = recognizer.recognize_once()   # 最初の発話（無音で区切られる1文）だけを認識する
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text
    if result.reason == speechsdk.ResultReason.Canceled:
        # 認証・エンドポイントの誤りはここに来る（error_details に理由が入る）
        raise RuntimeError(f"STT 失敗: Canceled {result.cancellation_details.error_details.splitlines()[0][:120]}")
    raise RuntimeError(f"STT 失敗: {result.reason}（NoMatch＝音声を聞き取れなかった）")


def process_with_llm(text: str) -> str:
    """② LLM：認識テキストに答える（読み上げる前提なので短く、記号なしで）。"""
    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)
    client = project.get_openai_client()
    resp = client.responses.create(
        model=MODEL_DEPLOYMENT,
        instructions="あなたは音声アシスタントです。読み上げるので、記号や箇条書きを使わず、2文以内の日本語で答えてください。",
        input=text,
    )
    return resp.output_text


def text_to_speech(text: str, out_path: str) -> None:
    """③ TTS：テキストを音声化して wav に書き出す。"""
    cfg = speech_config()
    cfg.speech_synthesis_voice_name = TTS_VOICE
    audio_config = speechsdk.audio.AudioOutputConfig(filename=out_path)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=audio_config)
    result = synthesizer.speak_text_async(text).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise RuntimeError(f"TTS 失敗: {result.reason} {result.cancellation_details.error_details.splitlines()[0][:120]}")


def main():
    args = sys.argv[1:]
    if args and args[0] == "make-input":
        text = args[1] if len(args) > 1 else "キーを使わずにアジュールへ接続する方法を教えてください。"
        text_to_speech(text, INPUT_WAV)
        print(f"[準備] {INPUT_WAV} を作りました（{wav_info(INPUT_WAV)}）")
        return
    if args and args[0] == "stt":
        path = args[1] if len(args) > 1 else "output.wav"
        print(f"[STT] {path}: {speech_to_text(path)}")
        return

    print(f"[入力] {INPUT_WAV}（{wav_info(INPUT_WAV) if os.path.exists(INPUT_WAV) else 'ファイルなし'}）")
    recognized = speech_to_text(INPUT_WAV)
    print(f"① STT: {recognized}")
    answer = process_with_llm(recognized)
    print(f"② LLM（{MODEL_DEPLOYMENT}）: {answer}")
    text_to_speech(answer, "output.wav")
    print(f"③ TTS: output.wav に書き出しました（{wav_info('output.wav')}）")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        print(f"[エラー] {type(ex).__name__}: {ex}")
