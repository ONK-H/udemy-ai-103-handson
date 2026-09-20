// L1-3 実践: Microsoft Foundry のインフラとモデルデプロイを IaC（Bicep）でコード化する。
//
// このテンプレートが作るもの（3つの ARM リソース）:
//   1. Microsoft.CognitiveServices/accounts            … Foundry リソース（親）
//   2. Microsoft.CognitiveServices/accounts/projects   … Foundry project（子＝作業空間）
//   3. Microsoft.CognitiveServices/accounts/deployments … モデルデプロイ
//
// 認証はキーレス（Entra ID）を強制する（disableLocalAuth=true でローカルキー認証を無効化）。
//
// ⚠️ API バージョン・モデル名/バージョン・SKU は「執筆時点のスナップショット」。
//    利用時に `az cognitiveservices account list-models` 等で再確認すること。
//    API バージョンは 2026-05-01（GA）で確認済み。最新の一覧は次で取れる:
//      az provider show -n Microsoft.CognitiveServices --query "resourceTypes[?resourceType=='accounts'].apiVersions[0:5]" -o tsv

@description('Foundry リソース（親）の名前。サブドメインにも使われるため「全世界で一意」。取得済みだと CustomDomainInUse で弾かれるので、末尾に自分用の英数字を足す。')
param foundryName string

@description('Foundry project（子）の名前。')
param projectName string = '${foundryName}-proj'

@description('リソースを作成するリージョン。')
param location string = resourceGroup().location

@description('デプロイするモデルのカタログ名（例: gpt-5.4-nano）。list-models で確認した値を入れる。')
param modelName string = 'gpt-5.4-nano'

@description('モデルのバージョン。list-models で確認した値を入れる（揮発情報）。')
param modelVersion string = '2026-03-17'

@description('モデルプロバイダー（format）。OpenAI モデルは OpenAI。')
@allowed([
  'OpenAI'
  'Microsoft'
  'Meta'
  'Mistral AI'
  'Cohere'
  'DeepSeek'
  'xAI'
  'AI21 Labs'
  'Core42'
])
param modelFormat string = 'OpenAI'

@description('呼び出しに使うデプロイ名（コードの model パラメータに渡す名前）。カタログ名と別でよい。')
param deploymentName string = 'chat'

@description('デプロイタイプ（SKU）。迷ったら GlobalStandard。')
@allowed([
  'GlobalStandard'
  'DataZoneStandard'
  'Standard'
  'GlobalProvisionedManaged'
  'ProvisionedManaged'
])
param skuName string = 'GlobalStandard'

@description('スループット容量（Standard 系は 1k TPM 単位の目安。要件に応じて調整）。')
param capacity int = 10

@description('コンテンツフィルターポリシー名。')
param contentFilterPolicyName string = 'Microsoft.DefaultV2'

// 1) Foundry リソース（親）: kind=AIServices, キーレス強制, プロジェクト管理を有効化
resource foundry 'Microsoft.CognitiveServices/accounts@2026-05-01' = {
  name: foundryName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    // Foundry project を作れるようにする
    allowProjectManagement: true
    // Entra ID 認証に必要なサブドメイン
    customSubDomainName: foundryName
    // キーレス強制（APIキー認証を無効化＝本講座の方針）
    disableLocalAuth: true
    // 既存リソースに適用し直すとき、ARM がこの値を要求する
    //（"PublicNetworkAccess is required for this resource." で失敗する）
    publicNetworkAccess: 'Enabled'
  }
}

// 2) Foundry project（子＝作業空間）
resource project 'Microsoft.CognitiveServices/accounts/projects@2026-05-01' = {
  parent: foundry
  name: projectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

// 3) モデルデプロイ（カタログのモデルを「呼べる状態」にし、デプロイ名を付ける）
resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2026-05-01' = {
  parent: foundry
  name: deploymentName
  sku: {
    name: skuName
    capacity: capacity
  }
  properties: {
    model: {
      format: modelFormat
      name: modelName
      version: modelVersion
    }
    raiPolicyName: contentFilterPolicyName
    // バージョン自動更新ポリシー（新しい版が出たときに追随するかの方針）:
    //   OnceNewDefaultVersionAvailable / OnceCurrentVersionExpired / NoAutoUpgrade
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

// 出力: 推論に使うエンドポイントとデプロイ名（.env に転記する）
@description('.env の PROJECT_ENDPOINT に入れる値。プロジェクト単位のエンドポイント（.../api/projects/<project>）。')
output projectEndpoint string = project.properties.endpoints['AI Foundry API']
@description('（参考）アカウント単位のエンドポイント。<resource>.cognitiveservices.azure.com 形式で、PROJECT_ENDPOINT には使えない別物。')
output foundryEndpoint string = foundry.properties.endpoint
@description('呼び出しに使うデプロイ名。')
output deploymentNameOut string = deployment.name
@description('Foundry project の名前。')
output projectNameOut string = project.name
