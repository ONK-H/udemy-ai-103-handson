"""L2-3 Foundry IQ：ナレッジベースを MCP ツールとしてエージェントに付け、質問する。

ナレッジベース（Azure AI Search）は MCP サーバーとして `knowledge_base_retrieve` ツールを公開している。
エージェントには MCPTool として付け、認証はプロジェクト接続（RemoteTool・プロジェクトのマネージド ID）に任せる。
認証はキーレス（DefaultAzureCredential + az login）。finally で会話とエージェントを消し、残っていないことを確かめる。
"""

import json
import os
import sys
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"]
SEARCH = os.environ["SEARCH_ENDPOINT"].rstrip("/")
KB_NAME = os.getenv("KNOWLEDGE_BASE_NAME", "product-kb")
CONNECTION = os.getenv("PROJECT_CONNECTION_NAME", "product-kb-mcp")
MODEL = os.getenv("MODEL_DEPLOYMENT", "gpt-5.4")
AGENT_NAME = "product-kb-agent"
MCP_ENDPOINT = f"{SEARCH}/knowledgebases/{KB_NAME}/mcp?api-version=2026-08-01-preview"
# 既定の3問（文書にある事実／2つの話題を1問で／文書に無い事実）。引数を渡すとその質問に差し替わる
QUESTIONS = [
    "この製品の保証期間と対応OSを教えて。",
    "延長保証のオプション名と、未開封品の返品期限は？",
    "この製品の重さは？",
]


def show_tool_calls(res) -> None:
    """ナレッジベースのツールを何回呼んだか、どんな検索語を渡したかを表示する。"""
    calls = [item for item in res.output if item.type == "mcp_call"]
    print(f"[ツール] mcp_call {len(calls)} 件")
    for call in calls:
        args = json.loads(call.arguments or "{}")
        print(f"  {call.name} ← {json.dumps(args, ensure_ascii=False)[:100]}")


def main() -> None:
    instructions = Path("agent_instructions.txt").read_text(encoding="utf-8")
    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    openai = project.get_openai_client()

    agent = conversation = None
    try:
        # 1) ナレッジベースを MCP ツールとして付けたエージェントを作る
        kb_tool = MCPTool(
            server_label="product-kb",
            server_url=MCP_ENDPOINT,
            require_approval="never",                  # 承認なしで呼ぶ（既定は always）
            allowed_tools=["knowledge_base_retrieve"],  # 呼べるツールをこれだけに絞る
            project_connection_id=CONNECTION,           # 認証は接続（プロジェクトのマネージド ID）に任せる
        )
        agent = project.agents.create_version(
            agent_name=AGENT_NAME,
            definition=PromptAgentDefinition(model=MODEL, instructions=instructions, tools=[kb_tool]),
        )
        print(f"エージェント作成: name={agent.name}, version={agent.version}")

        # 2) 会話を作り、質問を続けて送る
        conversation = openai.conversations.create()
        ref = {"agent_reference": {"name": agent.name, "type": "agent_reference"}}
        for question in sys.argv[1:] or QUESTIONS:
            print(f"\nあなた> {question}")
            response = openai.responses.create(conversation=conversation.id, input=question, extra_body=ref)
            show_tool_calls(response)
            print(f"AI> {response.output_text}")

    except Exception as ex:  # 教育目的の素朴なエラーハンドリング
        print(f"[エラー] {str(ex).splitlines()[0][:200]}")
    finally:
        # 3) 後片付け：会話とエージェントを消す（ナレッジベースと接続は消えない）
        if conversation:
            openai.conversations.delete(conversation.id)
        if agent:
            project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
        left = [a for a in project.agents.list() if a.name == AGENT_NAME]
        print(f"\n後片付け: エージェント {len(left)} 件が残っています")


if __name__ == "__main__":
    main()
