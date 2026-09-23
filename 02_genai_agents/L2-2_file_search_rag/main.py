"""L2-2 File Search ツールで PDF にグラウンディングする RAG。

ベクトルストア作成 → 文書アップロード（自動チャンク化・ベクトル化）→
File Search ツール付きエージェント作成 → 文書に基づく回答（引用つき）。
認証はキーレス（DefaultAzureCredential + az login）。
File Search は追加課金あり。finally で作ったものを必ず削除し、残っていないことを確かめる。
"""

import os
import sys
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FileSearchTool, PromptAgentDefinition
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-5.4")
DOC_PATH = Path(os.getenv("DOC_PATH", "product_info.pdf")).resolve()
AGENT_NAME = "file-search-rag-agent"
STORE_NAME = "ProductInfoStore"
# 既定の2問（1問目は文書にある事実、2問目は文書に無い事実）。引数を渡すとその質問に差し替わる
QUESTIONS = [
    "この製品の保証期間と対応OSを教えて。",
    "この製品の重さは？",
]


def show_grounding(res) -> None:
    """File Search を呼んだ回数と、回答に付いた引用（file_citation）を表示する。"""
    calls = [item for item in res.output if item.type == "file_search_call"]
    cites = []
    for item in res.output:
        if item.type != "message":
            continue
        for part in item.content:
            for ann in getattr(part, "annotations", None) or []:
                if ann.type == "file_citation":
                    cites.append(getattr(ann, "filename", None) or ann.file_id)
    print(f"[検索] file_search_call {len(calls)} 件")
    print(f"[引用] {len(cites)} 件" + (f" {', '.join(sorted(set(cites)))}" if cites else ""))


def main() -> None:
    if not PROJECT_ENDPOINT:
        raise SystemExit("PROJECT_ENDPOINT が未設定です。.env を確認してください。")
    if not DOC_PATH.exists():
        raise SystemExit(f"文書が見つかりません: {DOC_PATH}")

    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    openai = project.get_openai_client()

    agent = vector_store = doc_file = conversation = None
    try:
        # 1) ベクトルストアを作り、文書をアップロード（自動でチャンク化・ベクトル化）
        vector_store = openai.vector_stores.create(name=STORE_NAME)
        with DOC_PATH.open("rb") as fh:
            doc_file = openai.vector_stores.files.upload_and_poll(vector_store_id=vector_store.id, file=fh)
        print(f"取り込み: {DOC_PATH.name} → status={doc_file.status}")

        # 2) File Search ツールを持つエージェントを作る（ベクトルストアはエージェントに1つまで）
        agent = project.agents.create_version(
            agent_name=AGENT_NAME,
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT,
                instructions=(
                    "あなたはアップロードされた文書に基づいて回答するアシスタントです。"
                    "file search で根拠を探し、文書に書かれていることだけを使って日本語で2行以内で答えてください。"
                    "文書に書かれていないことは「文書に記載がありません」と答えてください。"
                ),
                tools=[FileSearchTool(vector_store_ids=[vector_store.id])],
            ),
            description="File Search による RAG エージェント",
        )
        print(f"エージェント作成: name={agent.name}, version={agent.version}")

        # 3) 会話を作り、文書にある事実と無い事実を続けて質問する
        conversation = openai.conversations.create()
        ref = {"agent_reference": {"name": agent.name, "type": "agent_reference"}}
        for question in sys.argv[1:] or QUESTIONS:
            print(f"\nあなた> {question}")
            response = openai.responses.create(conversation=conversation.id, input=question, extra_body=ref)
            show_grounding(response)
            print(f"AI> {response.output_text}")

    except Exception as ex:  # 教育目的の素朴なエラーハンドリング
        print(f"[エラー] {ex}")
    finally:
        # 4) 後片付け：会話・エージェント・ベクトルストア・アップロードした文書ファイルを消し、残りを数える
        if conversation:
            openai.conversations.delete(conversation.id)
        if agent:
            project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
        if vector_store:
            openai.vector_stores.delete(vector_store.id)
        if doc_file:
            openai.files.delete(doc_file.id)  # ベクトルストアを消しても、文書ファイル自体は Files に残るため
        stores = [v for v in openai.vector_stores.list() if v.name == STORE_NAME]
        files = [f for f in openai.files.list() if f.filename == DOC_PATH.name]
        agents = [a for a in project.agents.list() if a.name == AGENT_NAME]
        print(f"\n後片付け: ベクトルストア {len(stores)} / ファイル {len(files)} / エージェント {len(agents)} 件が残っています")


if __name__ == "__main__":
    main()
