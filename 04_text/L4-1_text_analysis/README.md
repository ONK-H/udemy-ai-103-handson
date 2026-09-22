# L4-1 実践: レビュー分析（感情＋エンティティ＋要約を構造化JSONで抽出）

同じレビュー群を、①生成プロンプト版（Responses APIの structured outputs）と②既製機能版（Azure Language の感情分析＋NER）の2通りで分析し、結果の違いを比較するハンズオンです。

> 対応レクチャー：実践 `L4-1-3`
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。APIキーは使いません。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | **生成プロンプト版**：Responses APIの `text.format`（json_schema／strict）で構造化JSON抽出 |
| `language_sdk_compare.py` | **既製機能版**：Azure Language（`azure-ai-textanalytics`）の感情分析＋オピニオンマイニング＋NER |
| `reviews.json` | 分析対象のレビュー文（複数件） |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- **`main.py` 用**：Foundry プロジェクト作成済み・構造化出力対応チャットモデル（`gpt-5-mini` など）をデプロイ済み
- **`language_sdk_compare.py` 用**：Azure AI Language リソース作成済み（`Cognitive Services Language Reader` 相当のロール）

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集（PROJECT_ENDPOINT・MODEL_DEPLOYMENT、比較版を使うなら AZURE_LANGUAGE_ENDPOINT も設定）

# 生成プロンプト版（出力をファイルにも残しつつ実行）
python main.py | Tee-Object -FilePath out.txt   # macOS/Linux: python main.py | tee out.txt

# 既製機能版（比較用）
python language_sdk_compare.py
```

`main.py` はレビューごとに「入力 → 分析結果(JSON)」を順に表示します。`language_sdk_compare.py` はレビューごとに「感情＋スコア」「側面（オピニオンマイニング）」「エンティティ」を表示します（要約は出ません。既製の要約機能は別APIです）。

## 注意点（試験の論点）
- 構造化出力（`json_schema`／`strict`）を使う場合、スキーマの**すべてのフィールドをrequiredにする**・**object には `additionalProperties: false` を付ける**という制約があります。
- システムメッセージは `instructions` パラメータで渡します（`system` の直後に `type` なしの `user` を並べると400エラーになるため）。
- 既製機能版（Language）は**文ごとの感情から文書全体のラベルを決める**、生成プロンプト版は**文書全体をモデルが読んで判定する**という仕組みの違いがあり、**同じレビューでも判定が割れることがあります**（「どちらが正しい」ではなく、何を基準にした判定かで選びます）。
- `language_sdk_compare.py` は言語を指定しないと既定の `"en"` として解析されるため、先に `detect_language` で言語検出してから渡しています。

## 期待される出力（例）
`main.py`：
```
=== レビュー 3 ===
入力: 新しいスマートウォッチを買いました。デザインは気に入っていますが、全体としては普通かなという感じです。
分析結果(JSON):
{
  "sentiment": "mixed",
  "entities": [
    {"text": "スマートウォッチ", "category": "製品"},
    {"text": "デザイン", "category": "機能"}
  ],
  "summary": "新しいスマートウォッチについて、デザインは気に入っていると評価しています。一方で全体としては「普通かな」としており、評価はやや控えめです。"
}
```

`language_sdk_compare.py`：
```
=== レビュー 3 ===
感情: positive  スコア: pos=1.00 neu=0.00 neg=0.00
  側面: デザイン(positive) ← 気に入っています
エンティティ: スマートウォッチ(Product)
```
（実際の値はモデル・実行ごとに変わります）

## つまずき
- **`[エラー] Error code: 404 - ... DeploymentNotFound ...`**：`.env` の `MODEL_DEPLOYMENT` が自分の環境に無いデプロイ名になっています（既定値 `gpt-5-mini` のまま等）。カタログ名ではなく実際のデプロイ名に直してください。認証自体は通っている（404はデプロイが見つからないだけ）点に注意。
- **環境変数を変えても反映されない**：`load_dotenv()` は既に設定済みの環境変数を上書きしません。シェルの環境変数（`$env:MODEL_DEPLOYMENT=...`）は `.env` より優先されます。
- **感情分析が期待とズレる**：既製版と生成版で判定基準が違うため、割れること自体は想定内です。

## 後片付け
- 呼んだトークン・API呼び出し分だけ課金されます（数円程度）。デプロイ自体は置いてあるだけでは課金されないので、他のレッスンで使わないなら削除は任意です。
