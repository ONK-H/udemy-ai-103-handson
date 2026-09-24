"""L5-1 実践(3/3): 作ったインデックスを Azure AI Search ツールとしてエージェントに付け、引用つきで答えさせる。

プロジェクトの Azure AI Search 接続（手順10で作る）を名前から ID に解決して使う。
質問ごとに、ツールの呼び出し件数と引用（url_citation）を表示し、最後にエージェントを消す。
認証はキーレス（az login + DefaultAzureCredential）。

使い方:
    python 03_ask_agent.py                  # 既定の3問
    python 03_ask_agent.py "返品の期限は？"   # 自分の質問を1つ
"""

import json
import os
import sys

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AzureAISearchTool, PromptAgentDefinition,
    AzureAISearchToolResource, AISearchIndexResource, AzureAISearchQueryType,
)
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from openai import APIStatusError

load_dotenv()
AGENT = "l5-search-agent"
QUESTIONS = sys.argv[1:] or [
    "テントの保証期間は？",
    "寝袋の快適使用温度と、テントの耐水圧を教えて。",
    "テントの価格は？",
]
INSTRUCTIONS = ("あなたは Contoso アウトドアのサポート担当です。必ず検索ツールで調べ、"
                "見つかった内容だけを根拠に日本語で2行以内で答えてください。"
                "根拠が見つからなければ「分かりません」と答えてください。")

project = AIProjectClient(endpoint=os.environ["PROJECT_ENDPOINT"], credential=DefaultAzureCredential())
openai = project.get_openai_client()

# 接続名 → 接続 ID（/subscriptions/…/connections/<名前>）を解決する
conn_id = project.connections.get(os.environ["SEARCH_CONNECTION_NAME"]).id

agent = project.agents.create_version(
    agent_name=AGENT,
    definition=PromptAgentDefinition(
        model=os.environ["MODEL_DEPLOYMENT"],
        instructions=INSTRUCTIONS,
        tools=[AzureAISearchTool(azure_ai_search=AzureAISearchToolResource(indexes=[
            AISearchIndexResource(
                project_connection_id=conn_id,
                index_name=os.environ["SEARCH_INDEX_NAME"],
                query_type=AzureAISearchQueryType.VECTOR_SEMANTIC_HYBRID,
                top_k=3,
            )]))],
    ),
)
print(f"エージェント作成: name={agent.name}, version={agent.version}")

try:
    for q in QUESTIONS:
        print(f"\nあなた> {q}")
        resp = openai.responses.create(
            input=q,
            extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
        )
        # 検索ツールの呼び出し。arguments に、モデルが作った検索クエリが入っている
        calls = [o for o in resp.output if o.type == "azure_ai_search_call"]
        print(f"[ツール] azure_ai_search_call {len(calls)} 件")
        for c in calls:
            print(f"  検索クエリ ← {json.loads(c.arguments).get('query', c.arguments)}")
        cites = []
        for o in resp.output:
            for c in getattr(o, "content", None) or []:
                for a in getattr(c, "annotations", None) or []:
                    if a.type == "url_citation":
                        cites.append(a.title or a.url)
        print(f"AI> {resp.output_text.strip()}")
        print(f"[引用] {len(cites)} 件 {sorted(set(cites))}")
except (HttpResponseError, APIStatusError) as e:
    # 400 "Access denied" は、手順5のロール（プロジェクトのマネージド ID → Search）の不足か未反映
    body = getattr(e, "body", None)
    msg = body.get("message") if isinstance(body, dict) else None
    print(f"エラー: {e.status_code} {(msg or str(e.message)).splitlines()[0][:160]}")
finally:
    project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
    left = [a for a in project.agents.list() if a.name == AGENT]
    print(f"\n後片付け: エージェント {len(left)} 件が残っています")
