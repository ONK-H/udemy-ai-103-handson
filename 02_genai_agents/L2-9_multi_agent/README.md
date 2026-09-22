# L2-9 実践: Microsoft Agent Framework でマルチエージェント協調（Magentic）

**マネージャー（主）エージェント**が、専門エージェント（調査担当・執筆担当）へ動的にタスクを委譲し、成果を統合する **Magentic** オーケストレーションのハンズオンです。`azure-ai-projects` ではなく **Microsoft Agent Framework**（`agent_framework`）を使います。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | Magentic ワークフローを組み立て、ストリーミングで進行を表示する |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ（`agent-framework-foundry`／`agent-framework-orchestrations`） |

## 前提
- Azure サブスクリプション ／ **`az login` 済み**（このコードは `AzureCliCredential` を使うため、`DefaultAzureCredential` 系の他の認証方法では代替できません）／ Python 3.11+
- Foundry プロジェクト作成済み・チャットモデルを1つデプロイ済み
- ⚠️ **Agent Framework は活発に進化中**。クラス名・引数が変わることがあるため、動かない場合は公式サンプルで最新APIを確認してください：https://github.com/microsoft/agent-framework/tree/main/python/samples/03-workflows/orchestrations
  （このコードの動作確認時点：`agent-framework-core` 1.19 / `-foundry` 1.13 / `-orchestrations` 1.2）

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集：FOUNDRY_PROJECT_ENDPOINT・FOUNDRY_MODEL（デプロイ名）

python main.py
```

## 期待される出力（例）
```
[manager] PLAN_CREATED

--- researcher ---
（調査担当の途中出力）

[manager] PROGRESS_LEDGER_UPDATED

--- writer ---
（執筆担当の途中出力）

--- 最終成果 ---
（マネージャーがまとめた最終成果）
```

## つまずき
- **`ModuleNotFoundError`**：`agent-framework-foundry` だけを入れても足りません。`requirements.txt` の全パッケージ（特に `agent-framework-orchestrations`）を入れてください。
- **`AttributeError: run_stream`**：旧 API です。現行は `workflow.run(task, stream=True)`（`run_stream()` は廃止）。
- **`gpt-4o-mini` は Deprecated**（2027-04-14 リタイア予定）。`.env.sample` の既定 `gpt-4.1-mini` を使ってください（最下位のクォータティアでも既定割り当てがあります）。
- **`message_id` が `None` になることがある**：このコードは話者（`executor_id`）の変化で見出しを出し直す実装にしてあります（公式サンプルの `message_id` 判定とは異なる回避策）。

## 後片付け
- 特別な後片付けは不要です（作成した Foundry リソースは他レッスンでも使うため削除しない）。
