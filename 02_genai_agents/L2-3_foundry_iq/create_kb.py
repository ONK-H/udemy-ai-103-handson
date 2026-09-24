"""L2-3 Foundry IQ：ナレッジソースとナレッジベースを Azure AI Search に作る（REST・キーレス）。

① ナレッジソース（Blob）を作る → Search がデータソース・スキルセット・インデックス・インデクサーを自動で作り、
   Blob の文書を取り込む（チャンク化・ベクトル化）。
② 取り込みが終わるまで状態を見る。
③ ナレッジベースを作る（ナレッジソースを束ね、クエリ計画に使う LLM と推論の強さを決める）。
`python create_kb.py --delete` で、ナレッジベース → ナレッジソースの順に消す（生成物もまとめて消える）。
"""

import os
import sys
import time

import requests
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

SEARCH = os.environ["SEARCH_ENDPOINT"].rstrip("/")           # https://<search>.search.windows.net
STORAGE_ID = os.environ["STORAGE_RESOURCE_ID"]               # /subscriptions/.../storageAccounts/<name>
CONTAINER = os.getenv("BLOB_CONTAINER", "l2-3-kb")
AOAI = os.environ["FOUNDRY_OPENAI_ENDPOINT"].rstrip("/")     # https://<foundry>.openai.azure.com
EMBEDDING = os.getenv("EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
KB_MODEL = os.getenv("KB_MODEL_DEPLOYMENT", "gpt-5.4")      # クエリ計画に使う LLM
KS_NAME = os.getenv("KNOWLEDGE_SOURCE_NAME", "product-blob-ks")
KB_NAME = os.getenv("KNOWLEDGE_BASE_NAME", "product-kb")
API = "2026-08-01-preview"  # LLM によるクエリ計画・推論の強さはプレビューの API で使う


def call(method: str, path: str, body: dict | None = None) -> dict:
    token = DefaultAzureCredential().get_token("https://search.azure.com/.default").token
    res = requests.request(method, f"{SEARCH}/{path}?api-version={API}", json=body,
                           headers={"Authorization": f"Bearer {token}"}, timeout=60)
    if res.status_code >= 400:
        raise SystemExit(f"[エラー] {method} {path} → {res.status_code} {res.text[:200]}")
    return res.json() if res.text else {}


def aoai(deployment: str) -> dict:
    return {"kind": "azureOpenAI",
            "azureOpenAIParameters": {"resourceUri": AOAI, "deploymentId": deployment, "modelName": deployment}}


def create() -> None:
    # ① ナレッジソース：Blob のありかと、取り込みに使う埋め込みモデル（認証は Search のマネージド ID）
    ks = call("PUT", f"knowledgesources/{KS_NAME}", {
        "name": KS_NAME, "kind": "azureBlob",
        "azureBlobParameters": {
            "connectionString": f"ResourceId={STORAGE_ID}",  # キーを持たず、マネージド ID で Blob を読む
            "containerName": CONTAINER,
            "ingestionParameters": {"embeddingModel": aoai(EMBEDDING),
                                    "contentExtractionMode": "minimal",
                                    "disableImageVerbalization": True},
        },
    })
    created = ks["azureBlobParameters"].get("createdResources") or {}
    print(f"① ナレッジソース {KS_NAME}：自動で作られたもの → {', '.join(created.values())}")

    # ② 取り込み（インデクサーの実行）が終わるまで待つ
    for _ in range(60):
        last = call("GET", f"knowledgesources/{KS_NAME}/status").get("lastSynchronizationState") or {}
        if last.get("endTime"):
            print(f"② 取り込み完了：処理 {last.get('itemsUpdatesProcessed')} 件 / 失敗 {last.get('itemsUpdatesFailed')} 件")
            break
        time.sleep(10)
    else:
        raise SystemExit("取り込みが10分で終わりませんでした。Search のマネージド ID のロールを確認してください。")

    # ③ ナレッジベース：ナレッジソースを束ね、クエリ計画の LLM と推論の強さ（low）を決める
    kb = call("PUT", f"knowledgebases/{KB_NAME}", {
        "name": KB_NAME,
        "description": "Contoso SmartHub X1 の製品情報",
        "knowledgeSources": [{"name": KS_NAME}],
        "models": [aoai(KB_MODEL)],
        "retrievalReasoningEffort": {"kind": "low"},
        "outputMode": "extractiveData",  # 回答の文章はエージェント側で作る。KB は根拠の抜き出しを返す
    })
    print(f"③ ナレッジベース {kb['name']}：推論の強さ={kb['retrievalReasoningEffort']['kind']}"
          f"、出力={kb['outputMode']}、ソース={[s['name'] for s in kb['knowledgeSources']]}")
    print(f"MCP エンドポイント：{SEARCH}/knowledgebases/{KB_NAME}/mcp?api-version={API}")


def delete() -> None:
    # ナレッジベースが参照している間はナレッジソースを消せないので、この順に消す
    call("DELETE", f"knowledgebases/{KB_NAME}")
    call("DELETE", f"knowledgesources/{KS_NAME}")
    left = [k["name"] for k in call("GET", "knowledgebases")["value"]] + \
           [k["name"] for k in call("GET", "knowledgesources")["value"]]
    print(f"削除しました。残り：{left or 'なし'}")


if __name__ == "__main__":
    delete() if "--delete" in sys.argv else create()
