# L5-3 Content Understanding：文書から構造化フィールド＋markdown

カスタムアナライザーを作り、文書（請求書 PDF）から構造化フィールド（key-value）と markdown を抽出するハンズオン。
フィールドの3方式 extract / generate / classify を1つずつ使い、confidence も確認する。

## 前提リソース
- Microsoft Foundry リソース（Content Understanding を含む）
- **モデルデプロイの既定（model deployment defaults）** の設定（生成能力を支える Foundry モデル）
  - Content Understanding Studio（https://contentunderstanding.ai.azure.com/settings）→ **+ Add resource** → リソースを選び、
    「必要なモデルを自動デプロイする」にチェック → **Next** → **Save**
  - `.env` の `CU_COMPLETION_MODEL`／`CU_EMBEDDING_MODEL` は、この既定に登録されている**モデル名**に合わせる
  - 対応モデル：https://learn.microsoft.com/azure/ai-services/content-understanding/service-limits#supported-generative-models
- 対応リージョン（japaneast など）：https://learn.microsoft.com/azure/ai-services/content-understanding/language-region-support

## RBAC（キーレス）
- 自分の ID に `Cognitive Services User`

## 手順
```bash
python -m venv .venv && source .venv/bin/activate   # Windows は .venv\Scripts\activate
pip install -r requirements.txt
cp .env.sample .env   # エンドポイント・DOCUMENT_URL を埋める
az login

python analyze_document.py
# → markdown（先頭500字）とフィールド（会社名/合計/要約/種別）＋confidence を表示し、アナライザーを削除
```

## 後片付け
アナライザーはスクリプトの finally で削除。検証専用に作った Foundry リソース／モデルデプロイは削除（リソースグループごとが確実）。

> ⚠️ Content Understanding は生成AI処理のため課金されます。API は GA `2025-11-01`（SDK 1.1.x の既定）。
> カスタムアナライザーの親にできるのは `prebuilt-document` / `prebuilt-image` / `prebuilt-audio` / `prebuilt-video` の4つだけ
> （プレビュー時代の `prebuilt-documentAnalyzer` は使えない）。SDK のクラス名・base_analyzer_id・API バージョンは
> 変化が速いので、`pip show azure-ai-contentunderstanding` と公式ドキュメントで最新を確認すること。
