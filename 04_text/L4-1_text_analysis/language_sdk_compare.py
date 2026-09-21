"""L4-1 実践(比較): Azure Language in Foundry Tools の既製機能版。

同じレビューを既製の感情分析（オピニオンマイニング含む）＋NERで分析し、
生成プロンプト版（main.py）との出力の違いを体感する。キーレス認証。
"""

import os
import json
from azure.identity import DefaultAzureCredential
from azure.ai.textanalytics import TextAnalyticsClient
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.getenv("AZURE_LANGUAGE_ENDPOINT")

# キーレス認証（Cognitive Services Language Reader 相当のロールが必要）
client = TextAnalyticsClient(endpoint=ENDPOINT, credential=DefaultAzureCredential())


def main():
    with open("reviews.json", encoding="utf-8") as f:
        texts = json.load(f)

    # 言語を指定しないと既定の "en" として解析され、日本語レビューを正しく判定できない。
    # 先に言語検出（detect_language）を行い、結果を各ドキュメントの language に渡す。
    detected = client.detect_language(texts)
    documents = [
        {"id": str(i), "text": t, "language": d.primary_language.iso6391_name if not d.is_error else "en"}
        for i, (t, d) in enumerate(zip(texts, detected), 1)
    ]

    # 感情分析（オピニオンマイニング＝側面ベースも有効化）
    sentiment_results = client.analyze_sentiment(documents, show_opinion_mining=True)
    # 固有表現認識（NER）
    entity_results = client.recognize_entities(documents)

    for i, (s, e) in enumerate(zip(sentiment_results, entity_results), 1):
        print(f"\n=== レビュー {i} ===")
        if s.is_error or e.is_error:
            print("[エラー] ドキュメント処理に失敗")
            continue
        print(
            f"感情: {s.sentiment}  スコア: pos={s.confidence_scores.positive:.2f} "
            f"neu={s.confidence_scores.neutral:.2f} neg={s.confidence_scores.negative:.2f}"
        )
        # 側面ベース（料理は良いが接客は悪い、等）
        for sentence in s.sentences:
            for opinion in sentence.mined_opinions:
                target = opinion.target
                assessments = ", ".join(a.text for a in opinion.assessments)
                print(f"  側面: {target.text}({target.sentiment}) ← {assessments}")
        # エンティティ
        ents = ", ".join(f"{ent.text}({ent.category})" for ent in e.entities)
        print(f"エンティティ: {ents}")


if __name__ == "__main__":
    main()
