"""L2-6 組み込みツール（Code Interpreter）付きの単一 Prompt agent。

PromptAgentDefinition（model/instructions/tools）でエージェントを定義し、
会話に紐づけて多ターンで対話する。計算は Code Interpreter が担う。
認証はキーレス（DefaultAzureCredential + az login）。finally で後片付け。
"""

import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, CodeInterpreterTool
from dotenv import load_dotenv

load_dotenv()
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-5-mini")


def main() -> None:
    if not PROJECT_ENDPOINT:
        raise SystemExit("PROJECT_ENDPOINT が未設定です。.env を確認してください。")

    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    openai = project.get_openai_client()

    agent = None
    try:
        # 1) 組み込みツール（Code Interpreter）付きの単一エージェントを作成
        agent = project.agents.create_version(
            agent_name="single-tool-agent",
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT,
                instructions=(
                    "あなたは丁寧な日本語のアシスタントです。"
                    "計算や数値の可視化が必要なときは Code Interpreter ツールを使ってください。"
                ),
                tools=[CodeInterpreterTool()],
            ),
            description="Code Interpreter 付き単一エージェント",
        )
        print(f"エージェント作成: name={agent.name}, version={agent.version}")

        # 2) 会話を作り、多ターンで対話（会話メモリ＝サーバ側保持）
        conversation = openai.conversations.create()
        ref = {"agent_reference": {"name": agent.name, "type": "agent_reference"}}

        for question in [
            "127 と 358 と 921 の合計と平均を計算して。",
            "その平均を3倍したらいくつ？",  # 前ターンの文脈を引き継ぐ
        ]:
            print(f"\nあなた> {question}")
            res = openai.responses.create(conversation=conversation.id, input=question, extra_body=ref)
            print(f"AI> {res.output_text}")

    except Exception as ex:  # 教育目的の素朴なエラーハンドリング
        print(f"[エラー] {ex}")
    finally:
        # 3) 後片付け（作成したエージェントのバージョンを削除）
        if agent:
            project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
            print("エージェントを削除しました")


if __name__ == "__main__":
    main()
