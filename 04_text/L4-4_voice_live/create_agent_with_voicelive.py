"""L4-4 実践: Voice Live 設定つき Foundry エージェントを作る／消す。

エージェントの metadata に Voice Live 設定（声・VAD・ノイズ抑制）を持たせる。
metadata の値は1つ512字までなので、設定の JSON を分割して入れる。キーレス認証。

使い方:
  python create_agent_with_voicelive.py          # 作る（定義が前回と同じなら、同じ版が返る）
  python create_agent_with_voicelive.py delete   # 後片付け：エージェントを全版まとめて消す
"""

import os
import sys
import json
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition

load_dotenv()

AGENT_NAME = os.getenv("AGENT_NAME", "ai103-voice-agent")
MODEL = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-5.4")


def chunk_config(config_json: str, limit: int = 512) -> dict:
    """Voice Live 設定を 512字ずつに分けて metadata に入れる（キー名に通し番号を付ける）。"""
    metadata = {"microsoft.voice-live.configuration": config_json[:limit]}
    remaining, n = config_json[limit:], 1
    while remaining:
        metadata[f"microsoft.voice-live.configuration.{n}"] = remaining[:limit]
        remaining, n = remaining[limit:], n + 1
    return metadata


def create(project: AIProjectClient) -> None:
    # Voice Live のセッション設定（声・話し終わりの検出・ノイズ抑制）
    voice_live_config = {
        "session": {
            "voice": {"name": "ja-JP-NanamiNeural", "type": "azure-standard"},
            "input_audio_transcription": {"model": "azure-speech"},
            "turn_detection": {
                "type": "azure_semantic_vad_multilingual",   # 日本語を含む多言語向け（azure_semantic_vad は英語向け）
                "end_of_utterance_detection": {"model": "semantic_detection_v1_multilingual"},
            },
            "input_audio_noise_reduction": {"type": "azure_deep_noise_suppression"},
            "input_audio_echo_cancellation": {"type": "server_echo_cancellation"},
        }
    }
    metadata = chunk_config(json.dumps(voice_live_config))

    agent = project.agents.create_version(
        agent_name=AGENT_NAME,
        definition=PromptAgentDefinition(
            model=MODEL,
            instructions="あなたは親切な日本語アシスタントです。声で読み上げるので、記号を使わず、2文以内で答えてください。",
        ),
        metadata=metadata,
    )
    print(f"Agent created: {agent.name} (version {agent.version})")
    print(f"  モデル: {MODEL} ／ Voice Live 設定: {len(json.dumps(voice_live_config))} 字 → metadata {len(metadata)} 個に分割")


def delete(project: AIProjectClient) -> None:
    project.agents.delete(agent_name=AGENT_NAME)
    left = [a.name for a in project.agents.list() if a.name == AGENT_NAME]
    print(f"Agent deleted: {AGENT_NAME}（同じ名前の残り: {len(left)} 件）")


def main() -> None:
    project = AIProjectClient(endpoint=os.environ["PROJECT_ENDPOINT"], credential=DefaultAzureCredential())
    if len(sys.argv) > 1 and sys.argv[1] == "delete":
        delete(project)
    else:
        create(project)


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        print(f"[エラー] {type(ex).__name__}: {str(ex).splitlines()[0][:160]}")
