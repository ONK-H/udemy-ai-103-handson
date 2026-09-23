"""L2-6 組み込みツール（Code Interpreter）付きの単一 Prompt agent。

PromptAgentDefinition（model/instructions/tools）でエージェントを定義し、
会話に紐づけて多ターンで対話する。計算は Code Interpreter が担う。
認証はキーレス（DefaultAzureCredential + az login）。finally で後片付け。
"""

import os
import sys
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, CodeInterpreterTool
from dotenv import load_dotenv

load_dotenv()
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-5.4")
AGENT_NAME = "single-tool-agent"
# 既定の2問。コマンドライン引数を渡すと、その質問（複数可）に差し替わる
QUESTIONS = [
    "1 から 10000 までの素数の個数と合計を計算して。",
    "その合計を個数で割ると？",  # 前ターンの文脈を引き継ぐ
]


def show_tool_calls(res) -> None:
    """応答に含まれるツール呼び出し（*_call）を表示する。Code Interpreter なら書いたコードの先頭も出す。"""
    calls = [item for item in res.output if item.type.endswith("_call")]
    print(f"[ツール] {len(calls)} 件" + "".join(f" {c.type}" for c in calls))
    for c in calls:
        code = (getattr(c, "code", None) or "").strip().splitlines()
        for line in code[:3]:
            print(f"    | {line}")


def main() -> None:
    if not PROJECT_ENDPOINT:
        raise SystemExit("PROJECT_ENDPOINT が未設定です。.env を確認してください。")

    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    openai = project.get_openai_client()

    agent = None
    try:
        # 1) 組み込みツール（Code Interpreter）付きの単一エージェントを作成
        agent = project.agents.create_version(
            agent_name=AGENT_NAME,
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT,
                instructions=(
                    "あなたは丁寧な日本語のアシスタントです。"
                    "計算や数値の可視化が必要なときは Code Interpreter ツールを使ってください。"
                    "答えは2行以内で簡潔に書いてください。"
                ),
                tools=[CodeInterpreterTool()],
            ),
            description="Code Interpreter 付き単一エージェント",
        )
        print(f"エージェント作成: name={agent.name}, version={agent.version}")

        # 2) 会話を作り、多ターンで対話（会話メモリ＝サーバ側保持）
        conversation = openai.conversations.create()
        ref = {"agent_reference": {"name": agent.name, "type": "agent_reference"}}

        for question in sys.argv[1:] or QUESTIONS:
            print(f"\nあなた> {question}")
            res = openai.responses.create(conversation=conversation.id, input=question, extra_body=ref)
            show_tool_calls(res)
            print(f"AI> {res.output_text}")

    except Exception as ex:  # 教育目的の素朴なエラーハンドリング
        print(f"[エラー] {ex}")
    finally:
        # 3) 後片付け（作成したエージェントのバージョンを削除し、残っていないことを確かめる）
        if agent:
            project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
            left = [a.name for a in project.agents.list() if a.name == agent.name]
            print(f"\nエージェントを削除しました（残り: {len(left)} 件）")


if __name__ == "__main__":
    main()
