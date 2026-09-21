"""L2-10 高リスク操作の前に人間承認を挟む（deterministic HITL）。

エージェントに低リスク（読み取り）と高リスク（削除）のツールを与え、
高リスク関数はオーケストレーター（アプリ）のコードで必ず承認を要求する。
承認するかをモデルに判断させない（deterministic HITL）。
認証はキーレス。finally で後片付け。

使い方:
    python main.py                        # 既定：「レコード 1002 を削除して。」（承認プロンプトが出る）
    python main.py "レコード 1001 を見せて。"  # 読み取りは承認なしで自動実行
"""

import os
import sys
import json
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, FunctionTool
from openai.types.responses.response_input_param import FunctionCallOutput
from dotenv import load_dotenv

load_dotenv()
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-4.1-mini")
MAX_TURNS = 5  # ツール呼び出しの往復の上限（無限ループ防止）

# 高リスク関数の集合（アプリ側で決定的に判定する＝モデル任せにしない）
HIGH_RISK = {"delete_record"}
_DB = {"1001": "山田", "1002": "佐藤"}


def get_record(record_id: str) -> dict:  # 低リスク（読み取り）
    return {"record_id": record_id, "name": _DB.get(record_id, "(なし)")}


def delete_record(record_id: str) -> dict:  # 高リスク（不可逆）
    _DB.pop(record_id, None)
    return {"deleted": record_id}


TOOL_IMPL = {"get_record": get_record, "delete_record": delete_record}

tools = [
    FunctionTool(name="get_record", description="レコードを読み取る",
                 parameters={"type": "object", "properties": {"record_id": {"type": "string"}},
                             "required": ["record_id"], "additionalProperties": False}, strict=True),
    FunctionTool(name="delete_record", description="レコードを削除する（高リスク）",
                 parameters={"type": "object", "properties": {"record_id": {"type": "string"}},
                             "required": ["record_id"], "additionalProperties": False}, strict=True),
]


def main() -> None:
    if not PROJECT_ENDPOINT:
        raise SystemExit("PROJECT_ENDPOINT が未設定です。.env を確認してください。")
    user_input = sys.argv[1] if len(sys.argv) > 1 else "レコード 1002 を削除して。"

    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    openai = project.get_openai_client()

    agent = None
    conversation = None
    try:
        agent = project.agents.create_version(
            agent_name="hitl-agent",
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT,
                instructions="ユーザーの依頼に応じて get_record / delete_record を使ってください。",
                tools=tools))
        conversation = openai.conversations.create()
        ref = {"agent_reference": {"name": agent.name, "type": "agent_reference"}}

        print(f"USER> {user_input}")
        res = openai.responses.create(input=user_input, conversation=conversation.id, extra_body=ref)

        for _ in range(MAX_TURNS):  # function_call が出なくなるまで往復する
            input_list = []
            for item in res.output:
                if getattr(item, "type", None) != "function_call":
                    continue
                args = json.loads(item.arguments)
                # ★ deterministic HITL：高リスク関数はアプリ側で必ず承認を挟む
                if item.name in HIGH_RISK:
                    ok = input(f"[承認] {item.name}({args}) を実行しますか？ (y/N): ").strip().lower() == "y"
                    result = TOOL_IMPL[item.name](**args) if ok else {"status": "denied_by_human", "name": item.name}
                else:
                    result = TOOL_IMPL[item.name](**args)  # 低リスクは自動実行
                    print(f"[自動実行] {item.name}({args}) -> {result}")
                input_list.append(FunctionCallOutput(
                    type="function_call_output", call_id=item.call_id,
                    output=json.dumps(result, ensure_ascii=False)))
            if not input_list:
                break
            res = openai.responses.create(input=input_list, conversation=conversation.id, extra_body=ref)

        print(f"AI> {res.output_text}")
    except Exception as ex:  # 教育目的の素朴なエラーハンドリング
        print(f"[エラー] {ex}")
    finally:
        if conversation:
            openai.conversations.delete(conversation_id=conversation.id)
        if agent:
            project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)


if __name__ == "__main__":
    main()
