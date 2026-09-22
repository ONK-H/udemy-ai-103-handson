# L1-3 実践: Foundry でのソリューション構築（インフラ／デプロイ／CI-CD）

モデルデプロイを **CLI／Bicep（IaC）で再現**し、**スモークテスト**で動作確認、さらに **GitHub Actions の雛形**で「評価ゲート → デプロイ」の流れを体験するハンズオンです。

> 対応レクチャー：座学 `L1-3-1`〜`L1-3-5`／実践 `L1-3-6`（CLI・Bicep・スモークテスト）・`L1-3-7`（評価ゲート付き CI/CD） ／ 対応スキル：S1.b-1,2,3,4
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。APIキーは使いません。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `deploy_model.azcli` | **Azure CLI** で Foundry リソース＋プロジェクト＋モデルデプロイを作成（手順を1行ずつ実行） |
| `main.bicep` | **IaC（Bicep）**：同じ構成を宣言的にコード化（`accounts`／`accounts/projects`／`accounts/deployments`） |
| `deploy_bicep.azcli` | Bicep の `what-if`（変更プレビュー）→ `create`（適用）コマンド |
| `main.py` | デプロイの**スモークテスト**（キーレスで推論し、デプロイの健全性を確認） |
| `.env.sample` | `main.py` 用の環境変数雛形（`PROJECT_ENDPOINT` / `DEPLOYMENT_NAME`） |
| `requirements.txt` | Python 依存パッケージ |
| `eval/dataset.json` | 評価ゲート用のデータセット（評価器＋テストクエリ） |
| `github-workflow-sample/evaluate-and-deploy.yml` | **GitHub Actions 雛形**：PR で評価ゲート、main で評価→デプロイ |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Azure CLI 2.80.0 以上（`az cognitiveservices` は本体同梱で拡張は不要。`account project` は 2.80.0 で追加。古ければ `az upgrade`）
- Python 3.11+
- 出力の整形は az 組み込みの `--query`（JMESPath）＋ `-o table/tsv/json` を使用（`jq` などの外部ツールは不要）
- シェルは **PowerShell** を前提（`.azcli` は PowerShell の変数記法 `$RG = "..."`・継続行はバッククォート ` で記述）。bash の場合は変数代入を `RG="..."`、継続行を `\` に読み替える。

## 進め方（どちらか or 両方）
**A. CLI で作る**
1. `deploy_model.azcli` の変数（`$RG` / `$ACCOUNT` / `$LOCATION` 等）を自分の値に置換。
2. 上から1コマンドずつ実行（手順4の `list-models` でモデル名/バージョンを確認してから手順5を実行）。

**B. Bicep（IaC）で作る**
1. `deploy_bicep.azcli` の変数を置換し、`what-if` → `create` を実行。
2. 出力（`projectEndpoint` / `deploymentNameOut`）を控える。`projectEndpoint` が `.env` の `PROJECT_ENDPOINT` に入る値（同時に出る `foundryEndpoint` はアカウント単位で別物）。

> ⚠️ A と B は**同じ構成**を作ります。両方を試すなら、片方は `what-if`（プレビュー）までに留めると、同名リソースの重複・衝突を避けられます。

**共通: スモークテスト（PowerShell）**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.sample .env
# .env に PROJECT_ENDPOINT と DEPLOYMENT_NAME を設定してから:
python main.py
```

**CI/CD 雛形（任意）**
- `github-workflow-sample/evaluate-and-deploy.yml` をリポジトリ直下 `.github/workflows/` にコピーし、OIDC（キーレス）と各リポジトリ変数を設定すると、PR で評価ゲート・main で評価→デプロイが動きます。

## 後片付け（任意）
Standard（従量）デプロイは、**モデルを置いておくだけでは課金されません**（課金は実際に呼び出したトークン分だけ）。慌てて削除する必要はなく、学習を続けるならそのまま使い回せます。片付けたくなったら、リソースグループごと削除すればまとめて消せます。
```powershell
az group delete --name ai103-l1-3-rg
```

## 注意（揮発情報）
- **モデル名/バージョン・SKU・API バージョン**は変動します。`list-models` と公式ドキュメントで都度確認。
- `microsoft/ai-agent-evals` と `azd` の hosted agent CI/CD は**プレビュー**。
