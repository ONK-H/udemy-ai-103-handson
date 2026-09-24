"""L2-3 Foundry IQ：ナレッジベースの retrieve を直接呼び、内側で何が起きたか（activity）を表示する。

エージェントの MCP ツール（knowledge_base_retrieve）が裏で呼んでいるのと同じ検索を、REST で1回だけ呼ぶ。
推論の強さが low 以上なら、LLM がクエリを計画してサブクエリに分け、ソースを並行して検索する。
"""

import json
import sys

from create_kb import KB_NAME, call

QUESTION = sys.argv[1] if len(sys.argv) > 1 else "延長保証のオプション名と、未開封品の返品期限は？"

result = call("POST", f"knowledgebases/{KB_NAME}/retrieve", {
    "messages": [{"role": "user", "content": [{"type": "text", "text": QUESTION}]}],
    "includeActivity": True,  # 検索の内訳（クエリ計画・サブクエリ・トークン）を返してもらう
})

print(f"質問: {QUESTION}")
for step in result.get("activity", []):
    if step["type"] == "modelQueryPlanning":
        print(f"[クエリ計画] {step['model']['modelName']}  入力 {step['inputTokens']} / 出力 {step['outputTokens']} トークン")
    elif step["type"] == "azureBlob":
        print(f"[検索] {step['knowledgeSourceName']} ← {step['azureBlobArguments']['search']}（{step['count']} 件）")
    elif step["type"] == "agenticReasoning":
        print(f"[推論の強さ] {step['retrievalReasoningEffort']['kind']}  推論トークン {step['reasoningTokens']}")

chunks = json.loads(result["response"][0]["content"][0]["text"])
print(f"[根拠] {len(chunks)} チャンク / 参照 {len(result.get('references', []))} 件（エージェントにはこの抜き出しが渡る）")
