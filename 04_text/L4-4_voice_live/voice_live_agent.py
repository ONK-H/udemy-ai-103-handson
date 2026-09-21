"""L4-4 実践: Voice Live に接続して音声エージェントと会話する（最小・接続まで）。

connect(...) に agent_name と project_name を渡してエージェントに接続し、
音声セッションを開始する。エージェント経由はキー認証不可＝Entra ID（キーレス）必須。

マイク取り込み・スピーカー再生の完全な実装は分量が大きいため、公式サンプル
（aka.ms/voicelive/github-python）をベースにする。本ファイルは「接続・セッション設定」までを示す。
"""

import os
import asyncio
from azure.identity.aio import DefaultAzureCredential
from azure.ai.voicelive.aio import connect
from azure.ai.voicelive.models import (
    RequestSession,
    Modality,
    InputAudioFormat,
    OutputAudioFormat,
    ServerEventType,
)
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.environ["VOICELIVE_ENDPOINT"]


async def main():
    # キーレス（Entra ID）。エージェント経由はキー認証不可。
    async with DefaultAzureCredential() as credential:
        # エージェントの指定は connect() のキーワード引数で渡す（agent_name + project_name）。
        # ※ 旧 SDK の agent_config={...} 辞書は azure-ai-voicelive 1.3 以降では無視される。
        async with connect(
            endpoint=ENDPOINT,
            credential=credential,
            api_version="2026-01-01-preview",
            agent_name=os.environ["AGENT_NAME"],
            project_name=os.environ["PROJECT_NAME"],
            # agent_version="...",     # 任意：固定したいバージョン
            # conversation_id="...",   # 任意：会話の継続
        ) as connection:
            # 音声セッション設定（声・VAD はエージェント側の Voice Live 設定を利用）
            session = RequestSession(
                modalities=[Modality.TEXT, Modality.AUDIO],
                input_audio_format=InputAudioFormat.PCM16,
                output_audio_format=OutputAudioFormat.PCM16,
            )
            await connection.session.update(session=session)
            print("VOICE ASSISTANT READY（この最小版はマイク/スピーカー入出力なし。Ctrl+C で終了）")
            # ここでマイク入力の送信とイベント受信（音声再生）ループを回す。
            # 完全なマイク/スピーカー I/O 実装はサンプルリポジトリ参照: aka.ms/voicelive/github-python
            async for event in connection:
                # event.type ごとに音声出力チャンクの再生・文字起こし表示などを処理する。
                # この最小版は受信したイベントの種類を表示するだけ（session.updated が出れば接続成功）。
                print(f"event: {event.type}")
                if event.type == ServerEventType.ERROR:
                    print(f"  エラー: {event.error.message}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n終了します。")
    except Exception as ex:
        print(f"[エラー] {ex}")
