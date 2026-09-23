"""L1-7 実践 (2): 安全性評価（risk & safety evaluators）を実行する。

ContentSafetyEvaluator で dataset.jsonl の質問と回答を採点し、4つの害
(violence / sexual / self_harm / hate_unfairness) のスコア（0〜7）とラベルを表示する。

ポイント:
- 認証は DefaultAzureCredential（キーレス）。
- risk & safety 評価器は Foundry がホストする評価サービスで動くので、採点役のモデルの
  デプロイ（deployment_name）は要らない。代わりにプロジェクトのエンドポイントと credential を渡す。
- 評価サービスが使えるリージョンは限られる（Japan East は非対応）。
  そのため評価用のプロジェクトを別に用意し、EVAL_PROJECT_ENDPOINT で指定する。
  未設定なら PROJECT_ENDPOINT（講座共通のプロジェクト）で試す。
- 評価は「判定」を返すだけで、ブロックはしない。最終判断は人（human-in-the-loop）。

必要ロール: 評価に使うプロジェクトに対する「Foundry User」(旧 Azure AI User)。
"""

import contextlib
import io
import json
import os

from azure.ai.evaluation import ContentSafetyEvaluator
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.getenv("EVAL_PROJECT_ENDPOINT") or os.getenv("PROJECT_ENDPOINT")
DATASET = os.path.join(os.path.dirname(__file__), "dataset.jsonl")
HARMS = ("violence", "sexual", "self_harm", "hate_unfairness")


def main() -> None:
    if not ENDPOINT:
        print("PROJECT_ENDPOINT が未設定です。.env を確認してください。")
        return
    print(f"評価に使うプロジェクト: {ENDPOINT.rsplit('/', 1)[-1]}")

    with contextlib.redirect_stderr(io.StringIO()):  # 実験的クラスの警告を画面に出さない
        evaluator = ContentSafetyEvaluator(
            azure_ai_project=ENDPOINT,  # プロジェクトのエンドポイント文字列
            credential=DefaultAzureCredential(),
            # しきい値は害ごとの引数（既定 3）。スコアがしきい値以下なら pass
        )

    with open(DATASET, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    for i, row in enumerate(rows, 1):
        print(f"\n[{i}] Q: {row['query'][:40]}")
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                result = evaluator(query=row["query"], response=row["response"])
        except Exception as ex:  # 教育目的でまとめて捕捉
            print(f"  エラー: {type(ex).__name__}: {str(ex).splitlines()[0][:110]}")
            continue
        cells = []
        for harm in HARMS:
            score = result.get(f"{harm}_score")
            cells.append(f"{harm}={score:g}({result.get(harm)})")
        print("  " + "  ".join(cells))
        for harm in HARMS:  # しきい値を超えて fail になった害だけ、理由を1行出す
            if result.get(f"{harm}_result") == "fail":
                print(f"  ⚠️ {harm} fail: {result.get(f'{harm}_reason', '')[:90]}")

    print("\n評価は判定を返すだけです。公開してよいかは人が判断します（human-in-the-loop）。")


if __name__ == "__main__":
    main()
