# L2-11 実践: エージェントにトレースを仕込み、失敗ケースを観測する

**server-side トレース**（Foundry の Application Insights 接続）と **client-side 計装**（OpenTelemetry）の両方を仕込み、**わざと存在しない型番（`ZZ9`）を照会させて失敗させ**、Foundry ポータルの Traces で span を辿って原因を分析するハンズオンです。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | `get_inventory` ツールに `@trace_function` を付け、OpenTelemetry を全件記録（`sampling_ratio=1.0`）で計装したエージェント |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ（`azure-monitor-opentelemetry` 等） |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- Foundry プロジェクト作成済み・チャットモデルを1つデプロイ済み
- **プロジェクトに Application Insights が接続済み**であること（管理 → プロジェクトの詳細 → 接続されているリソース で確認。共有プロジェクトは接続済み）

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集：PROJECT_ENDPOINT・MODEL_DEPLOYMENT

python main.py
# conversation id が表示され、「確認できたら Enter を押してください」で止まる。
# この間に Foundry ポータル → Agents → traced-agent → Traces を開いてトレースを確認する（取り込みに2〜5分）。
# 確認できたら Enter を押すとエージェントが削除される。
```

## 期待される出力（例）
```
[tool] get_inventory -> {'error': 'unknown product_code: ZZ9'}
AI> ZZ9 という型番は在庫データに見つかりませんでした。
conversation id: ...
Foundry ポータルの Agents → traced-agent → Traces で trace を確認（取り込みに2〜5分）
確認できたら Enter を押してください（エージェントを削除して終了）>
```

## つまずき
- **Traces タブが見当たらない**：Foundry ポータルのトレース画面は**エージェント向け**。ビルド → エージェント → 対象のエージェントを開いた中の「トレース」タブにある（エージェント一覧の直下ではない）。
- **`code.*` で足した属性が Application Insights に出ない**：エクスポーターの仕様。`code.` 以外の名前（このコードでは `app.tool_error`）で属性を足す。
- **span が出ない／間引かれる**：既定のサンプラーは1秒あたり数トレース程度に間引く。このコードは `sampling_ratio=1.0` で全件記録する設定済み。
- **Enter を押す前にエージェントを消してしまうと**、ポータルの Traces から辿れなくなる。確認が終わってから Enter を押すこと。

## 後片付け
- エージェントは Enter を押した後、`finally` で削除されます。Application Insights・conversation は他レッスンでも使うため削除しません。
