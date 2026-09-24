"""L4-4 実践: Voice Live でエージェントと「声で」1往復する（マイク・スピーカー無しでも動く版）。

 ・入力：音声ファイル（input.wav）を、マイクの代わりに Voice Live へ少しずつ送る
 ・出力：エージェントの声を reply.wav に保存し、文字起こしとイベントの流れを表示する
エージェント経由の接続はキー認証不可＝Entra ID（キーレス）必須。

使い方:
  python voice_live_agent.py make-input "質問の文"   # Azure Speech の TTS（REST）で質問の音声 input.wav を作る
  python voice_live_agent.py                         # input.wav を送って、返事を reply.wav に保存する
"""

import os
import sys
import wave
import base64
import asyncio
from collections import Counter
from dotenv import load_dotenv
from azure.identity.aio import DefaultAzureCredential
from azure.ai.voicelive.aio import connect
from azure.ai.voicelive.models import (
    RequestSession,
    Modality,
    InputAudioFormat,
    OutputAudioFormat,
    ServerEventType,
)

load_dotenv()

ENDPOINT = os.getenv("VOICELIVE_ENDPOINT")
INPUT_WAV = os.getenv("INPUT_WAV", "input.wav")
REPLY_WAV = os.getenv("REPLY_WAV", "reply.wav")
RATE = 24000                  # Voice Live の PCM16 は 24kHz・16bit・モノラル
CHUNK = RATE * 2 // 10        # 0.1 秒分（バイト）


def wav_info(path: str) -> str:
    """wav の長さとサイズ（動画では音が聞こえないので、数字で確かめる）。"""
    with wave.open(path, "rb") as w:
        sec = w.getnframes() / w.getframerate()
    return f"{sec:.1f} 秒・{os.path.getsize(path):,} バイト"


def make_input(text: str) -> None:
    """マイクの代わりの入力音声を、Azure Speech の TTS（REST）で作る（24kHz・16bit・モノラル）。
    キーレス：Entra ID のトークンを Bearer で渡す（カスタムドメインの endpoint が前提）。"""
    import urllib.request
    from azure.identity import DefaultAzureCredential as SyncCredential

    token = SyncCredential().get_token("https://cognitiveservices.azure.com/.default").token
    ssml = f'<speak version="1.0" xml:lang="ja-JP"><voice name="ja-JP-KeitaNeural">{text}</voice></speak>'
    req = urllib.request.Request(
        ENDPOINT.rstrip("/") + "/tts/cognitiveservices/v1",
        data=ssml.encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
            "User-Agent": "ai103-handson",
        },
    )
    with urllib.request.urlopen(req) as res, open(INPUT_WAV, "wb") as f:
        f.write(res.read())
    print(f"入力の音声を作りました: {INPUT_WAV}（{wav_info(INPUT_WAV)}）")


def one_line(text: str) -> str:
    """改行や連続した空白を1つの空白にまとめる（画面に1行で出すため）。"""
    return " ".join(text.split())


async def send_audio(connection) -> None:
    """input.wav をマイクの代わりに 0.1 秒ずつ送り、最後に無音を足して「話し終わり」を知らせる。"""
    with wave.open(INPUT_WAV, "rb") as w:
        pcm = w.readframes(w.getnframes())
    pcm += b"\x00" * (RATE * 2 * 2)   # 2 秒の無音（話し終わりの検出＝VAD に任せる）
    for i in range(0, len(pcm), CHUNK):
        await connection.input_audio_buffer.append(audio=base64.b64encode(pcm[i:i + CHUNK]).decode())
        await asyncio.sleep(0.02)
    print(f"  → 音声を送り終えました（{len(pcm) // CHUNK} 回に分けて送信）")


async def talk() -> None:
    if not os.path.exists(INPUT_WAV):
        raise FileNotFoundError(f"{INPUT_WAV} が見つかりません（先に make-input で作る）")
    reply = bytearray()
    counts: Counter = Counter()
    # キーレス（Entra ID）。エージェントの指定は connect() のキーワード引数で渡す。
    async with DefaultAzureCredential() as credential:
        async with connect(
            endpoint=ENDPOINT,
            credential=credential,
            api_version="2026-01-01-preview",
            agent_name=os.environ["AGENT_NAME"],
            project_name=os.environ["PROJECT_NAME"],
        ) as connection:
            # 宣言するのは入出力の形だけ。声や VAD はエージェント側の Voice Live 設定を使う。
            await connection.session.update(session=RequestSession(
                modalities=[Modality.TEXT, Modality.AUDIO],
                input_audio_format=InputAudioFormat.PCM16,
                output_audio_format=OutputAudioFormat.PCM16,
            ))
            sender = None
            async for event in connection:
                counts[event.type] += 1
                if event.type == ServerEventType.SESSION_UPDATED:
                    print("[1] session.updated … 接続・認証・エージェント指定が通った")
                    sender = asyncio.create_task(send_audio(connection))
                elif event.type == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED:
                    print("[2] speech_started … 話し始めを検出")
                elif event.type == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED:
                    print("[3] speech_stopped … 話し終わりを検出（ここで応答が始まる）")
                elif event.type == ServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED:
                    print(f"    あなた（文字起こし）: {one_line(event.transcript)}")
                elif event.type == ServerEventType.RESPONSE_AUDIO_DELTA:
                    reply.extend(event.delta)          # 声の断片（PCM16）を順に貯める
                elif event.type == ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DONE:
                    print(f"    エージェント（声の文字起こし）: {one_line(event.transcript)}")
                elif event.type == ServerEventType.RESPONSE_DONE:
                    print("[4] response.done … 1往復が完了")
                    break
                elif event.type == ServerEventType.ERROR:
                    print(f"[エラーイベント] {event.error.message}")
                    break
            if sender:
                sender.cancel()
    if reply:
        with wave.open(REPLY_WAV, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(bytes(reply))
        print(f"返事の音声を保存しました: {REPLY_WAV}（{wav_info(REPLY_WAV)}）")
    print(f"受け取った声の断片（response.audio.delta）: {counts[ServerEventType.RESPONSE_AUDIO_DELTA]} 個")


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "make-input":
            make_input(sys.argv[2] if len(sys.argv) > 2 else "おすすめの休日の過ごし方を一つ教えてください。")
        else:
            asyncio.run(talk())
    except KeyboardInterrupt:
        print("\n終了します。")
    except Exception as ex:
        print(f"[エラー] {type(ex).__name__}: {str(ex).splitlines()[0][:160]}")
