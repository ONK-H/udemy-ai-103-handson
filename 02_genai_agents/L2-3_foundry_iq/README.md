# L2-3 Foundry IQ ハンズオン（ポータル主体）

このレッスンは **Microsoft Foundry ポータル**での操作が主体です（PoC は無料枠で最短）。コードよりも、knowledge base を作ってエージェントに接続する一連の流れを体験します。

## ポータル手順（推奨）
1. **Foundry ポータル**（https://ai.azure.com）にサインイン。**New Foundry** トグルを ON。
2. プロジェクトを作成/選択 → 上部 **Build**。
3. **Knowledge** タブ：
   - agentic retrieval 対応の **Azure AI Search サービス**を作成/接続。
   - **knowledge source** を1つずつ追加して **knowledge base** を作成。
   - **reasoning effort**（minimal/low/medium）を設定（複雑クエリは medium）。
4. **Agents** タブ：
   - エージェントを作成 → 作成した **knowledge base を接続**。
   - システムプロンプト（`agent_instructions.txt` 参照）を設定。
5. **playground** で、取り込んだデータにしかない情報を質問し、出典付き回答を確認。

## CLI 版（Search・ストレージ・ロールをコマンドで作る場合）

ポータルでクリックする代わりに、Azure AI Search（Basic）とストレージをCLIで作り、ロールを付与してから、ポータルで knowledge base を作る手順です。**Search は時間課金**なので、検証が終わったら必ず削除してください。

```powershell
# az が古いときだけ： $env:PATH="$HOME/azcli/bin:"+$env:PATH

# 自分の環境に合わせて変更
$RG="<resource-group>"; $LOC="japaneast"
$FOUNDRY="<foundry-resource-name>"; $PROJECT="<project-name>"
$SEARCH="<search-service-name>"; $ST="<storage-account-name>"

# Search（Basic・マネージドID）とストレージを作成
az search service create -n $SEARCH -g $RG -l $LOC --sku basic --identity-type SystemAssigned --auth-options aadOrApiKey --aad-auth-failure-mode http401WithBearerChallenge
az storage account create -n $ST -g $RG -l $LOC --sku Standard_LRS --allow-blob-public-access false
az storage container create --account-name $ST -n l2-3-kb --auth-mode login
az storage blob upload --account-name $ST -c l2-3-kb -f ./product_info.md -n product_info.md --auth-mode login

# ロール付与（Search のMI → ストレージ・Foundry、プロジェクトのMI → Search）
$SEARCH_ID  = az search service show -n $SEARCH -g $RG --query id -o tsv
$SEARCH_MI  = az search service show -n $SEARCH -g $RG --query identity.principalId -o tsv
$ST_ID      = az storage account show -n $ST -g $RG --query id -o tsv
$FOUNDRY_ID = az cognitiveservices account show -n $FOUNDRY -g $RG --query id -o tsv
$PROJECT_MI = az resource show --ids "$FOUNDRY_ID/projects/$PROJECT" --query identity.principalId -o tsv

az role assignment create --assignee-object-id $SEARCH_MI  --assignee-principal-type ServicePrincipal --role "Storage Blob Data Reader"  --scope $ST_ID
az role assignment create --assignee-object-id $SEARCH_MI  --assignee-principal-type ServicePrincipal --role "Cognitive Services User"   --scope $FOUNDRY_ID
az role assignment create --assignee-object-id $PROJECT_MI --assignee-principal-type ServicePrincipal --role "Search Index Data Reader"  --scope $SEARCH_ID

# ロール反映に5〜10分待ってから、ポータルで knowledge base を作成（上の「ポータル手順」の3以降へ）

# --- 検証が終わったら必ず削除（Searchは時間課金） ---
az search service delete -n $SEARCH -g $RG --yes
az storage account delete -n $ST -g $RG --yes
```

- `az storage blob upload --auth-mode login` には自分に **Storage Blob Data Contributor** が要ります（Owner だけでは足りないことがあります）。
- `$PROJECT_MI` が空ならプロジェクトのシステム割り当てマネージドIDが無効です。ポータルでプロジェクトのIDを有効化してください。
- ロール付与の反映に**5〜10分**かかります。付けた直後に進めず待ってください。

## プログラム接続（MCP 経由・概観）
- knowledge sources → knowledge base 作成（Azure AI Search 側）。
- プロジェクトに **RemoteTool** の project connection を作成（マネージドIDで KB の MCP エンドポイントを指す）。
- エージェントに **MCP ツール**を追加（KB は `knowledge_base_retrieve` MCP ツールを公開）。
- 詳細：https://learn.microsoft.com/azure/foundry/agents/how-to/foundry-iq-connect
- E2E サンプル：https://github.com/Azure-Samples/azure-search-python-samples/tree/main/agentic-retrieval-pipeline-example

## 後片付け
- knowledge base / knowledge source / エージェントを削除。
- Azure AI Search サービスを削除（無料枠でも枠を占有）。検証専用ならリソースグループごと削除。

> ⚠️ ロール名リネーム：**Foundry User / Foundry Project Manager**（旧 Azure AI User / Azure AI Project Manager。権限は不変）。
