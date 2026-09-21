"""L4-3 実践: 音声パイプライン（STT → LLM → TTS）。

 ① STT: 音声（マイク or input.wav）を Azure Speech でテキスト化
 ② LLM: Responses API でテキストを処理
 ③ TTS: 応答テキストを Azure Speech で音声化（output.wav）
キーレス認証（Entra ID）。STT は token_credential、TTS は aad# トークン（TTS も token_credential で書ける）。
"""

import os
import azure.cognitiveservices.speech as speechsdk
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from dotenv import load_dotenv

load_dotenv()

SPEECH_ENDPOINT = os.getenv("SPEECH_ENDPOINT")
SPEECH_REGION = os.getenv("SPEECH_REGION")
SPEECH_RESOURCE_ID = os.getenv("SPEECH_RESOURCE_ID")
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-5-mini")
INPUT_WAV = os.getenv("INPUT_WAV") or ""
TTS_VOICE = os.getenv("TTS_VOICE", "ja-JP-NanamiNeural")

credential = DefaultAzureCredential()


def speech_to_text() -> str:
    """① STT：音声をテキスト化（キーレス：token_credential + カスタムドメインendpoint）。"""
    speech_config = speechsdk.SpeechConfig(token_credential=credential, endpoint=SPEECH_ENDPOINT)
    speech_config.speech_recognition_language = "ja-JP"
    if INPUT_WAV:
        if not os.path.exists(INPUT_WAV):
            raise FileNotFoundError(f"{INPUT_WAV} が見つかりません（.env の INPUT_WAV を空にするとマイク入力）")
        audio_config = speechsdk.audio.AudioConfig(filename=INPUT_WAV)
    else:
        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
        print("マイクに話しかけてください…")
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    result = recognizer.recognize_once()
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text
    if result.reason == speechsdk.ResultReason.Canceled:
        # 認証・エンドポイントの誤りはここに来る（error_details に理由が入る）
        raise RuntimeError(f"STT 失敗: Canceled {result.cancellation_details.error_details}")
    raise RuntimeError(f"STT 失敗: {result.reason}（NoMatch＝音声を聞き取れなかった）")


def process_with_llm(text: str) -> str:
    """② LLM：認識テキストを処理（例：丁寧な日本語で応答）。"""
    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential)
    client = project.get_openai_client()
    resp = client.responses.create(
        model=MODEL_DEPLOYMENT,
        instructions="あなたは丁寧な日本語アシスタントです。入力に簡潔に応答してください。",
        input=text,
    )
    return resp.output_text


def text_to_speech(text: str, out_path: str = "output.wav") -> None:
    """③ TTS：応答テキストを音声化（キーレス：aad#{resourceId}#{token} を auth_token に）。"""
    # 補足：現行の Speech SDK では SpeechSynthesizer も STT と同じ
    #   SpeechConfig(token_credential=credential, endpoint=SPEECH_ENDPOINT) で書ける（公式の推奨形）。
    #   ここでは REST API と共通の「aad#リソースID#トークン」形式を見せるため auth_token を使う。
    token = credential.get_token("https://cognitiveservices.azure.com/.default")
    auth_token = f"aad#{SPEECH_RESOURCE_ID}#{token.token}"
    speech_config = speechsdk.SpeechConfig(auth_token=auth_token, region=SPEECH_REGION)
    speech_config.speech_synthesis_voice_name = TTS_VOICE
    audio_config = speechsdk.audio.AudioOutputConfig(filename=out_path)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    result = synthesizer.speak_text_async(text).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise RuntimeError(f"TTS 失敗: {result.reason} {result.cancellation_details.error_details}")
    print(f"音声を {out_path} に出力しました。")


def main():
    recognized = speech_to_text()
    print(f"① STT: {recognized}")
    answer = process_with_llm(recognized)
    print(f"② LLM: {answer}")
    text_to_speech(answer)


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        print(f"[エラー] {ex}")
