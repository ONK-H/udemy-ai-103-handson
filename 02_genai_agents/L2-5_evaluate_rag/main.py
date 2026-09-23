"""L2-5 RAG の回答を評価器でスコア化する。

azure-ai-evaluation の evaluate() で Groundedness（根拠性）・Relevance（関連性）・
Coherence（一貫性）の3つの評価器を data.jsonl にまとめて実行し、
1件ずつのスコアと pass/fail を表で表示する。

- AI 支援の評価器は、採点役（judge）の LLM に「採点用のプロンプト」を送って点を付けさせる。
  採点役の設定が model_config。認証はキーレス（credential=DefaultAzureCredential()）。
- スコアは 1〜5。しきい値（既定 3）以上なら pass、未満なら fail。
  pass/fail を決めるのは採点役ではなく、このしきい値。
"""

import argparse
import contextlib
import io
import logging
import os
import re
import sys
import unicodedata

from azure.ai.evaluation import (
    CoherenceEvaluator,
    GroundednessEvaluator,
    RelevanceEvaluator,
    evaluate,
)
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

METRICS = ["groundedness", "relevance", "coherence"]


def short(text: str, n: int) -> str:
    text = str(text).replace("\n", " ")
    return text if len(text) <= n else text[: n - 1] + "…"


def pad(text: str, width: int) -> str:
    """全角を2桁と数えて右を空白で埋める（日本語の列をそろえる）"""
    w = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    return text + " " * max(1, width - w)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=int, default=3,
                    help="pass にする最低スコア（1〜5。既定 3）")
    args = ap.parse_args()

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("JUDGE_DEPLOYMENT", "gpt-4.1-mini")
    if not endpoint:
        sys.exit("AZURE_OPENAI_ENDPOINT が未設定です。.env を確認してください。")

    # 採点役（judge）の LLM。api_key は書かず、credential でキーレスにする
    model_config = {
        "azure_endpoint": endpoint,
        "azure_deployment": deployment,
        "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
    }
    credential = DefaultAzureCredential()
    evaluators = {
        "groundedness": GroundednessEvaluator(model_config, credential=credential, threshold=args.threshold),
        "relevance": RelevanceEvaluator(model_config, credential=credential, threshold=args.threshold),
        "coherence": CoherenceEvaluator(model_config, credential=credential, threshold=args.threshold),
    }

    print(f"採点役: {deployment} ／ しきい値: {args.threshold}（1〜5 のスコアがこれ以上なら pass）")
    print("評価中…（data.jsonl の各行を、3つの評価器がそれぞれ採点します）")
    log = io.StringIO()
    try:
        # evaluate() は進捗や実行の要約を大量に出すので、画面には表だけを出す
        logging.disable(logging.CRITICAL)
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            result = evaluate(data="data.jsonl", evaluators=evaluators)
    except Exception as e:  # 採点役の設定ミスなどは1行で見せる
        sys.exit(f"評価に失敗しました: {short(e, 300)}")
    finally:
        logging.disable(logging.NOTSET)

    rows = result.get("rows", [])
    print()
    print(pad("No", 4) + pad("質問", 16) + pad("根拠性", 13) + pad("関連性", 13) + "一貫性")
    for i, row in enumerate(rows, 1):
        cells = []
        for m in METRICS:
            score = row.get(f"outputs.{m}.{m}")
            res = row.get(f"outputs.{m}.{m}_result")
            cells.append(f"{score if score is not None else '-'} {res or 'error'}")
        q = short(row.get("inputs.query", ""), 7)
        print(pad(str(i), 4) + pad(q, 16) + "".join(pad(c, 13) for c in cells))

    # fail になった行は、採点役の理由（reason）を短く出す（画面に収まるよう先頭2件まで）
    fails = [(i, m, row.get(f"outputs.{m}.{m}_reason", ""))
             for i, row in enumerate(rows, 1) for m in METRICS
             if row.get(f"outputs.{m}.{m}_result") == "fail"]
    for i, m, reason in fails[:2]:
        print(f"\n[No{i} {m} の理由] {short(reason, 150)}")
    if len(fails) > 2:
        print(f"\n（fail はほかに {len(fails) - 2} 件）")

    if any(row.get(f"outputs.{m}.{m}_result") is None for row in rows for m in METRICS):
        # 採点役の API が返したエラーの本文（message）だけを取り出す
        msgs = re.findall(r"Error code: (\d+) - .*?'message': \\?[\"'](.+?)\\?[\"'], 'type'", log.getvalue())
        print("\n採点に失敗した評価器があります（error の欄）。")
        if msgs:
            code, msg = msgs[-1]
            print(f"  採点役の API のエラー: {code} {short(msg, 150)}")

    metrics = result.get("metrics", {})
    print("\n=== 集計（3件の平均と pass の割合） ===")
    for m in METRICS:
        avg = metrics.get(f"{m}.{m}")
        rate = metrics.get(f"{m}.binary_aggregate")
        avg_s = f"{avg:.2f}" if isinstance(avg, (int, float)) else "-"
        rate_s = f"{rate:.2f}" if isinstance(rate, (int, float)) else "-"
        print(f"{m:<13} 平均 {avg_s} ／ pass の割合 {rate_s}")


if __name__ == "__main__":
    main()
