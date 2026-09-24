"""L5-3 準備: Content Understanding の「モデルの既定（defaults）」を設定して確認する。

カスタムアナライザーは、コードの中では「モデル名」（例: gpt-5.4）しか持たない。
そのモデル名を、このリソースのどのデプロイで動かすかは、リソース側の「既定」が決める。
既定は Foundry リソースごとに1回設定すればよい（PATCH /contentunderstanding/defaults）。

使い方:
  python set_defaults.py          # .env のモデル名 → デプロイ名 を既定に登録して、結果を表示
  python set_defaults.py --show   # 登録せずに、今の既定だけを表示
認証はキーレス（az login + DefaultAzureCredential）。
"""

import os
import sys

from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()
ENDPOINT = os.environ["CONTENTUNDERSTANDING_ENDPOINT"]
# モデル名（カタログの名前）と、自分のデプロイ名。この講座ではデプロイ名をモデル名と同じにしている
COMPLETION_MODEL = os.getenv("CU_COMPLETION_MODEL", "gpt-5.4")
EMBEDDING_MODEL = os.getenv("CU_EMBEDDING_MODEL", "text-embedding-3-large")
COMPLETION_DEPLOYMENT = os.getenv("CU_COMPLETION_DEPLOYMENT", COMPLETION_MODEL)
EMBEDDING_DEPLOYMENT = os.getenv("CU_EMBEDDING_DEPLOYMENT", EMBEDDING_MODEL)


def main() -> None:
    client = ContentUnderstandingClient(endpoint=ENDPOINT, credential=DefaultAzureCredential())

    if "--show" not in sys.argv:
        # モデル名 → デプロイ名 の対応を、リソースの既定に登録する（既にあるキーは上書き、無いキーはそのまま）
        client.update_defaults(model_deployments={
            COMPLETION_MODEL: COMPLETION_DEPLOYMENT,
            EMBEDDING_MODEL: EMBEDDING_DEPLOYMENT,
        })
        print("既定を登録しました")

    print("\n--- このリソースの既定（モデル名 → デプロイ名）---")
    for model, deployment in (client.get_defaults().model_deployments or {}).items():
        print(f"  {model} → {deployment}")

    # 親にする prebuilt-document が、どのモデル名に対応しているか
    supported = client.get_analyzer("prebuilt-document").supported_models
    completion = list(supported.completion or [])
    print(f"\nprebuilt-document が対応する補完モデル: {len(completion)} 種類"
          f"（{COMPLETION_MODEL} は{'対応' if COMPLETION_MODEL in completion else '一覧に無い'}）")


if __name__ == "__main__":
    try:
        main()
    except HttpResponseError as e:
        inner = getattr(getattr(e, "error", None), "innererror", None) or {}
        print(f"エラー: HTTP {e.status_code} {inner.get('code', '')}")
        print(f"  {str(inner.get('message', ''))[:110]}")
        print("エンドポイント（services.ai.azure.com）と、データ操作のロール（Foundry User など）を確認してください。")
        sys.exit(1)
