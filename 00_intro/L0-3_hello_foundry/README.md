# L0-3 実践: Hello, Foundry

Microsoft Foundry プロジェクトに**キーレス**（`DefaultAzureCredential`）で接続し、Responses API でチャットモデルを1回呼んで応答を表示する、最小のサンプルです。

> 対応レクチャー：実践 `L0-3-2` ／ 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。APIキーは使いません。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | Foundry プロジェクトへキーレス接続し、Responses API を1回呼ぶ最小サンプル |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- Azure サブスクリプション（従量課金）／`az login` 済み
- Python 3.11+、Azure CLI 2.80.0 以上（`az version` で確認。`az cognitiveservices account project` コマンドは 2.80.0 で追加）

## 進め方（コピペで実行できます）

### 1. サインイン先を確かめる
```bash
az account show --query "{subscription:name, state:state}" -o table
```

### 2. クォータティアを確認する（ポータルには出ないので API で見る）
```bash
az rest --method get \
  --url "https://management.azure.com/subscriptions/$(az account show --query id -o tsv)/providers/Microsoft.CognitiveServices/quotaTiers?api-version=2026-09-01"
```
`properties.currentTierName` が返ります。**最下位ティア（Free Tier / Tier 0）**だった場合、既定クォータが付くのは `gpt-4.1-mini` / `gpt-5-mini` / `o4-mini` / `text-embedding-3-small` の4モデルだけです。その場合は以下の `gpt-5.4-nano` を `gpt-4.1-mini` に読み替えてください（`.env` の `MODEL_DEPLOYMENT` も同じ名前にします。手順・学習目的は変わりません）。

> ⚠️ `api-version=2023-05-01` は404になります。上記の `2026-09-01` が通ります（api-version は更新が速いので、失敗したら現行の値を確認してください）。

### 3. リソースグループを作る
```bash
az group create --name rg-ai103-hello --location japaneast
```

### 4. Foundry リソースを作る
```bash
az cognitiveservices account create \
    --name ai103-hello-foundry \
    --resource-group rg-ai103-hello \
    --kind AIServices \
    --sku S0 \
    --location japaneast \
    --custom-domain ai103-hello-foundry \
    --assign-identity \
    --allow-project-management true
```
- `--custom-domain` はグローバルに一意です（使用済みなら `CustomDomainInUse`）。
- `--assign-identity` が無いと、次のプロジェクト作成が `managed identity must be enabled` で失敗します。
- ⚠️ **既存アカウントに対してこのコマンドを再実行すると** `(BadRequest) PublicNetworkAccess is required for this resouce`（Azure側のスペルミスもそのまま）で失敗します。`--public-network-access Enabled` という引数は存在しません（`unrecognized arguments`）。**既にリソースがある場合は `create` を再実行せず**、`az cognitiveservices account show --name ai103-hello-foundry --resource-group rg-ai103-hello` で状態を確認するだけにしてください。

### 5. プロジェクトを作る
```bash
az cognitiveservices account project create \
    --name ai103-hello-foundry \
    --resource-group rg-ai103-hello \
    --project-name hello-foundry-project \
    --location japaneast
```
> ⚠️ 親のリソースを指す引数は `--account-name` ではなく **`--name`/`-n`** です（`--account-name` はこのサブコマンドでは通らず `the following arguments are required: --name/-n` になります）。`project create` は `--project-name` も必須です。

### 6. チャットモデルをデプロイする
```bash
az cognitiveservices account deployment create \
    --name ai103-hello-foundry \
    --resource-group rg-ai103-hello \
    --deployment-name gpt-5.4-nano \
    --model-name gpt-5.4-nano \
    --model-version "2026-03-17" \
    --model-format OpenAI \
    --sku-capacity 10 \
    --sku-name GlobalStandard

# 確認（provisioningState が Succeeded になればOK）
az cognitiveservices account deployment show \
    --name ai103-hello-foundry \
    --resource-group rg-ai103-hello \
    --deployment-name gpt-5.4-nano
```
> ⚠️ `--model-version` と対応 SKU は更新されます。収録時点の値が古い場合は、ポータルのモデルカードか `az cognitiveservices model list --location japaneast --query "[?model.name=='gpt-5.4-nano'].{version:model.version,skus:join(',',model.skus[].name)}" -o table` で現行の値を確認して指定してください。

### 7. プロジェクトのエンドポイントを取得する
```bash
az cognitiveservices account project show \
    --name ai103-hello-foundry \
    --resource-group rg-ai103-hello \
    --project-name hello-foundry-project \
    --query 'properties.endpoints."AI Foundry API"' -o tsv
```
- ⚠️ **Build > Models のデプロイ詳細に出るエンドポイントとは別物**です。そちらを貼ると `main.py` は404になります。ポータルなら、プロジェクトの**ホーム（welcome）画面**に出る「プロジェクト エンドポイント」を使ってください。

### 8. ローカル環境をセットアップする
```bash
cd udemy-ai-103-handson/00_intro/L0-3_hello_foundry
python -m venv .venv
. .venv/Scripts/activate          # macOS/Linux は: source .venv/bin/activate
pip install -r requirements.txt
```
> ⚠️ `azure-ai-projects` は **2.x（新／Foundry プロジェクト）**を使います。1.x（classic／Hub）とは互換性がありません。`pip show azure-ai-projects` で2.0以上を確認してください。

### 9. `.env` を用意する
```bash
cp .env.sample .env               # Windows: copy .env.sample .env
```
`.env` を開き、手順7で取得したエンドポイントを `PROJECT_ENDPOINT` に、手順6のデプロイ名を `MODEL_DEPLOYMENT` に設定します（`.env` は `.gitignore` 対象。コードに直書き・コミットしないでください）。

### 10. 実行する
```bash
python main.py
```

## 期待される出力（例）
```
✅ キーレスで接続: https://ai103-hello-foundry.services.ai.azure.com/api/projects/hello-foundry-project

----- モデル応答 -----
（モデルからの説明文が続く）
```
呼び出しが成功したことと、答えの内容が正しいことは別です。モデルはそれらしい文章を自信を持って書くことがあるので、内容が正しいかは自分で確認してください。

## つまずき
- **`401`（認証エラー）**：`az login` していない／トークン期限切れ。`az login` をやり直し、`az account show` で正しいサブスクリプションか確認。
- **`403`**：プロジェクトに **Foundry User** ロールが割り当たっているか確認。
- **`404`（モデルが見つからない）**：`.env` の `MODEL_DEPLOYMENT` は**カタログ名ではなくデプロイ名**。実際のデプロイ名と一致しているか確認。
- **`az cognitiveservices account create` が `(InsufficientQuota)` で失敗**：モデルのTPMではなく**リソース作成レベルの別クォータ**です。無料試用版・学生サブスクリプションで起きやすく、従量課金への切り替えかサポートリクエストが必要です。
- **`insufficient quota` でデプロイできない**：手順2のクォータティア確認に戻り、`gpt-4.1-mini` 等の最下位ティアで使えるモデルに読み替えてください。

## 後片付け
このプロジェクトは以降のレッスンでも使います。学習を続けるなら残しておいて構いません（Standard デプロイは呼び出さない限り課金されません）。完全に片付ける場合：
```bash
az group delete --name rg-ai103-hello --yes --no-wait
```
