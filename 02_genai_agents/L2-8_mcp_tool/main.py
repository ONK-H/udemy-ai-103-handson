"""L2-8 リモート MCP サーバーのツールをエージェントに接続して呼ぶ。

MCPTool でリモート MCP サーバー（GitHub）を宣言し、require_approval="always" で
承認フロー（mcp_approval_request → mcp_approval_response）を自分のコードで処理する。
MCP サーバーへの認証（GitHub の PAT）はコードに書かず、プロジェクトの接続に持たせる。
Foundry への認証はキーレス（az login ＋ DefaultAzureCredential）。finally で後片付け。

使い方:
    python main.py                        # 既定：「私の GitHub のユーザー名は？」（承認プロンプトが出る。y で呼ぶ、それ以外は拒否）
    python main.py "別の質問"             # 質問を差し替える
"""

import os
import sys
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, MCPTool
from openai.types.responses.response_input_param import McpApprovalResponse
from dotenv import load_dotenv

load_dotenv()
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-5.4")
MCP_CONNECTION_NAME = os.getenv("MCP_CONNECTION_NAME")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "https://api.githubcopilot.com/mcp")
AGENT_NAME = "mcp-agent"
ALLOWED_TOOLS = ["get_me"]  # 許可リスト：この講座で使うツールだけに絞る（最小権限）


def count_items(response) -> str:
    """応答に含まれる項目の種類と件数（例：mcp_list_tools 1 件 / mcp_approval_request 1 件）"""
    kinds: dict[str, int] = {}
    for item in response.output:
        t = getattr(item, "type", "?")
        kinds[t] = kinds.get(t, 0) + 1
    return " / ".join(f"{k} {v} 件" for k, v in kinds.items())


def main() -> None:
    if not PROJECT_ENDPOINT or not MCP_CONNECTION_NAME:
        raise SystemExit("PROJECT_ENDPOINT / MCP_CONNECTION_NAME を .env に設定してください。")
    question = sys.argv[1] if len(sys.argv) > 1 else "私の GitHub のユーザー名は？"

    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    openai = project.get_openai_client()

    # 接続は名前と種類だけ確かめる（資格情報の値は取り出さない）
    conn = project.connections.get(MCP_CONNECTION_NAME)
    print(f"接続: {conn.name}（種類: {conn.type}）")

    # リモート MCP サーバーをツールとして宣言する。呼び出しのたびに承認を求める
    tool = MCPTool(
        server_label="github",
        server_url=MCP_SERVER_URL,
        require_approval="always",
        allowed_tools=ALLOWED_TOOLS,
        project_connection_id=MCP_CONNECTION_NAME,
    )

    agent = conversation = None
    try:
        agent = project.agents.create_version(
            agent_name=AGENT_NAME,
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT,
                instructions="必要に応じて MCP ツールを使ってください。答えは1〜2行で簡潔に書いてください。",
                tools=[tool],
            ),
        )
        print(f"エージェント作成: name={agent.name}, version={agent.version}, model={MODEL_DEPLOYMENT}")
        conversation = openai.conversations.create()
        ref = {"agent_reference": {"name": agent.name, "type": "agent_reference"}}

        # 1) 質問する → ツールを呼ぶ前に、承認要求（mcp_approval_request）が返る
        print(f"\nUSER> {question}")
        response = openai.responses.create(conversation=conversation.id, input=question, extra_body=ref)
        print(f"[応答1] {count_items(response)}")
        for item in response.output:
            if getattr(item, "type", None) == "mcp_list_tools":  # サーバーから取り寄せたツールの一覧
                names = [t.name for t in (item.tools or [])]
                print(f"[ツール一覧] server={item.server_label} {len(names)} 件: {', '.join(names)}")

        # 2) 承認要求を人間が確かめて、承認か拒否かを返す
        input_list = []
        for item in response.output:
            if getattr(item, "type", None) == "mcp_approval_request" and item.id:
                print(f"[承認要求] server={item.server_label} tool={item.name} arguments={item.arguments}")
                approve = input("このMCPツール呼び出しを承認しますか？ (y/N): ").strip().lower() == "y"
                input_list.append(McpApprovalResponse(
                    type="mcp_approval_response", approve=approve, approval_request_id=item.id))

        # 3) 承認応答を返して、続きを処理させる
        if input_list:
            response = openai.responses.create(
                input=input_list, previous_response_id=response.id, extra_body=ref)
            print(f"[応答2] {count_items(response)}")
            for item in response.output:
                if getattr(item, "type", None) == "mcp_call":
                    status = f"エラー: {item.error}" if getattr(item, "error", None) \
                        else f"結果 {len(item.output or '')} 文字"
                    print(f"[MCP 呼び出し] tool={item.name} {status}")
        print(f"AI> {response.output_text}")

    except Exception as ex:  # 教育目的の素朴なエラーハンドリング（1行で表示）
        print(f"[エラー] {type(ex).__name__}: {str(ex).splitlines()[0][:150]}")
    finally:
        # 会話と、作成したエージェントの版を削除し、残っていないことを確かめる
        if conversation:
            openai.conversations.delete(conversation_id=conversation.id)
        if agent:
            project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
            left = [a.name for a in project.agents.list() if a.name == agent.name]
            print(f"会話とエージェントを削除しました（残り: {len(left)} 件）")


if __name__ == "__main__":
    main()
