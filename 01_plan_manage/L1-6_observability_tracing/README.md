# L1-6 実践: トレースを仕込んで Application Insights で可視化

自分の生成AIアプリに **OpenTelemetry トレース**を仕込み、**Foundry の Traces** と **Azure Monitor Application Insights** で「**呼び出し・トークン・レイテンシ**」を可視化するハンズオンです。

> 対応レクチャー：座学 `L1-6-1`(可観測性の基盤と性能監視)／`L1-6-2`(品質・安全性・グラウンディング・データ監視)、実践 `L1-6-3` ／ 対応スキル：S1.c-2,3
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。APIキーは使いません。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `trace_app.py` | 計測を有効化(`AIProjectInstrumentor`)→Application Insights へエクスポート(`configure_azure_monitor`)→`@trace_function` で自作関数を span 化→Responses API で推論 |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- **Foundry プロジェクト**にチャットモデルをデプロイ済み（`MODEL_DEPLOYMENT` はデプロイ名）
- プロジェクトに **Application Insights を接続済み**（Foundry ポータル：Build → Agents → Traces → Connect。見当たらなければ Manage → Project details → Connected resources）
- `az login` 済み ／ Python 3.10+（`azure-ai-projects` 2.0.0 以上）
- ロール：プロジェクトに **Contributor** 以上＋接続先 Application Insights に **Log Analytics Reader**（保護テーブルなら追加で **Privileged Monitoring Data Reader**）

## 進め方
```bash
python -m venv .venv
. .venv/Scripts/activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env             # Windows: copy .env.sample .env
# .env を編集してから:
python trace_app.py
```

## 期待される出力（例）
```
Q: Microsoft Foundry の可観測性とは何ですか？1文で答えてください。
A: ...(モデルの回答)...

Q: デプロイしたモデルが動かないエラーの一般的な切り分け手順を3つ挙げてください。
A: ...(モデルの回答)...

--- トレース送信完了。Foundry の Traces / Application Insights で確認できます(反映に2〜5分) ---
```

実行後、**Foundry ポータル → Build → Agents → Traces タブ** に `l1-6-trace-demo` を親とするトレースが現れ、
`classify-question`（自作 span）と Responses API 呼び出しの span が並びます（反映に2〜5分）。

## Application Insights（KQL）で確認
Azure ポータルで接続先の Application Insights → Logs で：
```kusto
// 依存関係(モデル呼び出し)の所要時間
dependencies
| where timestamp > ago(1h)
| project timestamp, name, duration, success
| order by timestamp desc
```
```kusto
// GenAI span の属性(トークン数など)を確認
dependencies
| where timestamp > ago(1h)
| extend d = parse_json(customDimensions)
| project timestamp, name, duration,
          input_tokens = d["gen_ai.usage.input_tokens"],
          output_tokens = d["gen_ai.usage.output_tokens"]
| order by timestamp desc
```
> 属性名(`gen_ai.usage.*` 等)は OpenTelemetry GenAI セマンティック規約に従う。版により名称が変わりうるので、実データの customDimensions を見て調整する。

## つまずきポイント
| 症状 | 対処 |
|---|---|
| span が出ない | `AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true` が `instrument()` の**前**に設定されているか（本コードは import 前に設定済み） |
| Application Insights に出ない | 接続文字列が正しいか、プロジェクトに App Insights が接続済みか。`Log Analytics Reader` ロールがあるか |
| メッセージ本文が span に出ない | `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`（本番は付けない） |
| `model not found` | `MODEL_DEPLOYMENT` が**デプロイ名**と一致しているか（カタログ名ではない） |
| 反映が遅い | 2〜5分かかる。数分待って再読み込み |

## 後片付け（課金回避）
- このハンズオンは**推論を数回**するだけ（数円程度）。
- トレースは **Application Insights（Log Analytics）に保存され、データ量・保持に応じて課金**される。検証用なら保持期間を短くするか、検証専用の Application Insights をリソースグループごと削除：`az group delete --name <rg>`。

## 注意（揮発情報）
- **GenAI トレースは実験的プレビュー**（span/属性が変わりうる）。`azure-ai-projects` は **2.0.0 以上**。
- 計測の環境変数名・既定値、Foundry ポータルのラベル（Build → Agents → Traces の配置）は変動。公式ドキュメントで都度確認。
