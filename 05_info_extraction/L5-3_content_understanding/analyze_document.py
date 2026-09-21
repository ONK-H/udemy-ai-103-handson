"""L5-3 実践: カスタムアナライザーで文書から構造化フィールド＋markdown を抽出。

フィールド方式 extract / generate / classify を1つずつ使う。
GA API（2025-11-01）版。認証はキーレス（az login + DefaultAzureCredential）。
"""

import os
import time
from azure.identity import DefaultAzureCredential
from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.ai.contentunderstanding.models import (
    ContentAnalyzer, ContentAnalyzerConfig, ContentFieldSchema, ContentFieldDefinition,
    ContentFieldType, GenerationMethod, AnalysisInput,
)
from dotenv import load_dotenv

load_dotenv()
ENDPOINT = os.environ["CONTENTUNDERSTANDING_ENDPOINT"]
DOCUMENT_URL = os.environ["DOCUMENT_URL"]
# アナライザーが使う Foundry モデル（デプロイ名ではなくカタログのモデル名）。
# 実際のデプロイへの対応付けは、リソースの「モデルデプロイの既定（defaults）」で行う
COMPLETION_MODEL = os.getenv("CU_COMPLETION_MODEL", "gpt-4.1")
EMBEDDING_MODEL = os.getenv("CU_EMBEDDING_MODEL", "text-embedding-3-large")


def main() -> None:
    client = ContentUnderstandingClient(
        endpoint=ENDPOINT, credential=DefaultAzureCredential())
    # アナライザーIDに使えるのは英数字・ドット・アンダースコアだけ（ハイフンは InvalidAnalyzerId）
    analyzer_id = f"l5_3_doc_analyzer_{int(time.time())}"

    # 1) スキーマ定義：extract / generate / classify を1つずつ
    field_schema = ContentFieldSchema(
        name="invoice_schema",
        description="請求書から会社名・合計・要約・種別を抽出",
        fields={
            "company_name": ContentFieldDefinition(
                type=ContentFieldType.STRING,
                method=GenerationMethod.EXTRACT,        # 原文を抜き出す
                description="請求元の会社名"),
            "total_amount": ContentFieldDefinition(
                type=ContentFieldType.NUMBER,
                method=GenerationMethod.EXTRACT,
                description="合計金額"),
            "document_summary": ContentFieldDefinition(
                type=ContentFieldType.STRING,
                method=GenerationMethod.GENERATE,       # AIが要約を生成
                description="文書の1文要約"),
            "document_type": ContentFieldDefinition(
                type=ContentFieldType.STRING,
                method=GenerationMethod.CLASSIFY,       # 分類
                description="文書の種別",
                enum=["invoice", "receipt", "contract", "other"]),
        },
    )
    analyzer = ContentAnalyzer(
        base_analyzer_id="prebuilt-document",   # 文書のベースアナライザー（GA の4種の1つ）
        description="L5-3 custom document analyzer",
        config=ContentAnalyzerConfig(
            enable_ocr=True,
            enable_layout=True,
            # GA では confidence / grounding は既定で返らない。明示的に有効化する
            estimate_field_source_and_confidence=True,
            return_details=True,
        ),
        field_schema=field_schema,
        # field_schema を持つ prebuilt-document 派生アナライザーでは必須
        models={"completion": COMPLETION_MODEL, "embedding": EMBEDDING_MODEL},
    )

    # 2) アナライザー作成（非同期LRO）
    print("アナライザーを作成中...")
    client.begin_create_analyzer(analyzer_id=analyzer_id, resource=analyzer).result()

    try:
        # 3) 解析
        print("文書を解析中...")
        result = client.begin_analyze(
            analyzer_id=analyzer_id,
            inputs=[AnalysisInput(url=DOCUMENT_URL)],
        ).result()

        content = result.contents[0]

        # 4) クリーンな markdown（RAG/エージェント向け）
        print("\n--- markdown（先頭500字）---")
        print((content.markdown or "")[:500])

        # 5) スキーマ準拠のフィールド（自動化/分析向け）＋confidence
        print("\n--- フィールド ---")
        for key in ("company_name", "total_amount", "document_summary", "document_type"):
            f = content.fields.get(key) if content.fields else None
            if f:
                conf = f" (confidence={f.confidence:.2f})" if getattr(f, "confidence", None) else ""
                print(f"  {key}: {f.value}{conf}")
    finally:
        # 6) 後片付け（アナライザー削除）
        client.delete_analyzer(analyzer_id=analyzer_id)
        print(f"\nアナライザー '{analyzer_id}' を削除しました")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 教育目的のエラーハンドリング
        print(f"エラー: {type(e).__name__}: {e}")
        print("Foundry のモデルデプロイ既定（CU_COMPLETION_MODEL / CU_EMBEDDING_MODEL が対応付いているか）、"
              "Cognitive Services User ロール、エンドポイント、DOCUMENT_URL を確認してください。")
        raise
