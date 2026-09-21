# L5-1 検索・グラウンディング：エンリッチしたインデックス → エージェント接続

スキルセット（Text Split + Azure OpenAI Embedding = integrated vectorization）で
Blob のサンプル文書をチャンク化・ベクトル化してインデックス化し、
そのインデックスを Foundry エージェントの **Azure AI Search ツール**として接続して、
引用つきでグラウンディング回答させるハンズオン。

## 前提リソース
- Azure AI Search（**Basic 以上**。Free はマネージドIDでの外部接続が使えないため、このキーレス構成では不可）
  - **API アクセス制御を「ロールベース」または「両方」にする**（既定は API キーのみ。`az search service update --auth-options aadOrApiKey ...`）
  - **システム割り当てマネージドID を有効化**（インデクサーが Blob と埋め込みモデルを読むため）
  - セマンティックランカーは既定で Free プラン（月の無料枠あり）。インデックス側のセマンティック構成はスクリプトが作る
- Microsoft Foundry プロジェクト ＋ Azure OpenAI 埋め込みモデル（例 `text-embedding-3-large`）＋ チャットモデル（例 `gpt-4.1-mini`）
- Azure Blob Storage（サンプル文書コンテナ）
- Foundry プロジェクトから Azure AI Search への**接続**（Foundry ポータル：プロジェクト → **Manage** → **Project details** → **Connected resources** → **Add connection** → Azure AI Search。認証はキーレス＝Microsoft Entra ID を選ぶ）

## RBAC（キーレス。自分と各マネージドIDに付与）
- 自分：検索サービスに `Search Service Contributor` ＋ `Search Index Data Contributor`
- 検索サービスのマネージドID：ストレージに `Storage Blob Data Reader`、埋め込みモデルのリソースに `Cognitive Services OpenAI User`
- Foundry リソース（アカウント）のシステム割り当てマネージドID：検索サービスに `Search Index Data Contributor` ＋ `Search Service Contributor`
  （公式の手順は「Foundry アカウントのマネージドID」、トラブルシュート表は「プロジェクトのマネージドID」と書いている。401/403 が出たらプロジェクトのマネージドIDにも付与する）

## 手順
```bash
python -m venv .venv && source .venv/bin/activate   # Windows は .venv\Scripts\activate
pip install -r requirements.txt
cp .env.sample .env   # 値を埋める
az login

# サンプル文書を Blob にアップロード
az storage blob upload-batch -d l5-1-docs -s ./docs --account-name <account> --auth-mode login

# 1) エンリッチインデックスを作成・実行
python 01_build_index.py

# 2) （Foundry ポータルで Azure AI Search 接続を作成後）エージェントに接続して質問
python 02_ask_agent.py
```

## 後片付け
検索オブジェクト（indexer → skillset → index → data source）と、検証用に作ったリソースを削除する。
検証専用ならリソースグループごと削除が確実。

> ⚠️ SDK のモデルクラス名・API バージョン・埋め込みモデル ID は変化が速い。
> `pip show azure-search-documents` と公式ドキュメントで最新を確認すること。
