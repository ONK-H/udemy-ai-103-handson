# L1-7 実践: ガードレール設定＋危険入力ブロック＋安全性評価

チャットアプリに **ガードレール（旧コンテンツフィルター）** を設定し、(1) 危険入力が**ブロック**されることをコードで確認し、(2) **安全性評価（risk & safety evaluators）** で応答の有害度をスコア化するハンズオンです。

> 対応レクチャー：座学 `L1-7-2`(Content Safety)／`L1-7-3`(ガードレール設定)／`L1-7-4`(評価・安全性評価) ／ 実践 `L1-7-6` ／ 対応スキル：S1.d-1,2
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。APIキーは使いません。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `block_demo.py` | Responses API を呼び、安全な入力＝正常応答＋`content_filters`注釈、危険な入力＝**400 `content_filter`** ブロックを確認 |
| `safety_eval.py` | `ContentSafetyEvaluator` で Q&A を採点（violence/sexual/self_harm/hate_unfairness のスコア・ラベル・reason） |
| `dataset.jsonl` | 安全性評価用のサンプル Q&A（安全な例＋有害な例） |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- **Foundry プロジェクト**にチャットモデルをデプロイ済み（`MODEL_DEPLOYMENT` はデプロイ名）
- `az login` 済み ／ Python 3.10+（`azure-ai-projects` 2.0.0 以上）
- ロール：プロジェクトに **Foundry User**（旧 Azure AI User）。安全性評価サービス対応リージョン（Japan East は非対応。East US 2／Sweden Central など）のプロジェクトであること
- （任意）ポータルで **Build → Guardrails** からカスタムガードレールを作成してデプロイに割り当てると、ブロック挙動を厳格化して試せる

## 進め方
```bash
python -m venv .venv
. .venv/Scripts/activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env             # Windows: copy .env.sample .env
# .env を編集してから:
python block_demo.py
python safety_eval.py
```

## 期待される出力（例）
`block_demo.py`：
```
===== A. 安全な入力 =====
結果: ✅ 正常応答 (ガードレールを通過)
応答: ガードレールは、有害な入力や出力を検知してブロックし...
content_filters 注釈:
  - source=prompt blocked=False
      hate: {"filtered": false, "severity": "safe"}
      ...

===== B. 危険な入力 (ブロックを期待) =====
結果: 🛡️ ガードレールにブロックされました (HTTP 400 / content_filter)
  → アプリ側では『この内容にはお答えできません』等の定型応答に差し替えるのが定石。
```
`safety_eval.py`：
```
[3] Q: How do I get revenge ...
    A: You should hurt them physically ...
  ⚠️ violence         score=5.0 label=Medium
       reason: The response promotes physical harm ...
```

## ポイント
- Responses API はガードレール注釈を**トップレベル `content_filters` 配列**で返す（Chat Completions の `prompt_filter_results`/`content_filter_results` とは形が違う）。SDK の型に無い拡張なので `model_dump()` の raw フィールドとして読む。
- **risk & safety 評価器はモデルデプロイ不要**（ホスト型 Foundry Evaluation サービス＝裏は Content Safety）。`azure_ai_project`（プロジェクトのエンドポイント文字列）＋ `credential` を渡す。
- 安全性評価は **0-7 スケール**でスコア＋ラベル＋**reason（説明）**を返す。**判定するだけで自動ブロックはしない → human-in-the-loop**。

## つまずきポイント
| 症状 | 対処 |
|---|---|
| 危険入力がブロックされない | デプロイのガードレールしきい値が緩い可能性。ポータルでカスタムガードレールを作り厳格化、`CUSTOM_GUARDRAIL_NAME` で上書きして再試行 |
| `content_filters` が出ない | 既定設定では Safe 時に省略されることがある。危険寄りの入力や注釈有効化で確認 |
| `safety_eval.py` で 403 / リージョンエラー | プロジェクトに **Foundry User** ロール、評価サービス対応リージョンか確認（Japan East は非対応。実測：`UserError: Single inline evaluations are not supported in the japaneast region`） |
| `model not found` | `MODEL_DEPLOYMENT` が**デプロイ名**と一致しているか（カタログ名ではない） |
| `azure_ai_project` 型エラー | バージョンにより dict 形式が必要な場合あり。`{"subscription_id":..., "resource_group_name":..., "project_name":...}` を試す |

## 後片付け（課金回避）
- 推論・評価を数回するだけ（数円程度）。
- 安全性評価は**ホスト型サービス呼び出し**で少額課金。ガードレール自体は**デプロイ単位**で残るので、検証用に作ったカスタムガードレールは不要なら削除（Build → Guardrails → 対象を選んで Delete。割り当て済みなら先に再割り当て）。

## 注意（揮発情報）
- 用語「**ガードレール（旧 content filters）**」「**Foundry User**（旧 Azure AI User）」。
- Responses API の `content_filters` は Foundry 拡張（SDK 非型）。`azure-ai-evaluation` の `azure_ai_project` 受理形式（エンドポイント文字列 / dict）と安全性評価の対応リージョンは版で変わりうる。公式ドキュメントで都度確認。
