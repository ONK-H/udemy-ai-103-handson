# L2-2 実践: File Search ツールで PDF/Markdown にグラウンディングする RAG

**File Search ツール**を使い、アップロードした文書（Markdown/PDF）に基づいて回答するエージェントを作るハンズオンです。ベクトルストア作成 → 文書アップロード（自動チャンク化・ベクトル化）→ File Search ツール付きエージェント作成 → 文書に基づく回答、の流れを1本の `main.py` で体験します。

> 対応レクチャー：実践 `L2-2-3`
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。APIキーは使いません。
> ⚠️ **File Search は追加課金があります**（ベクトルストアの保存・クエリ）。`main.py` は `finally` でエージェント・ベクトルストアを必ず削除します。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | ベクトルストア作成・文書アップロード・File Search エージェント作成・質問・後片付けの一連 |
| `product_info.md` | 読み込ませるサンプル文書（製品情報） |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ（`openai` は `azure-ai-projects` 2.x が依存として入れるため明示不要） |

## 前提
- **Foundry プロジェクト**にチャットモデルをデプロイ済み（`MODEL_DEPLOYMENT` は**デプロイ名**。カタログ名ではない）
- `az login` 済み ／ Python 3.10+
- ロール：プロジェクトに **Foundry User**

## 進め方
```bash
python -m venv .venv
. .venv/bin/Activate.ps1        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.sample .env             # Windows: copy .env.sample .env
```

`.env` の `PROJECT_ENDPOINT` は、`az` が使えるなら次のコマンドで取得できます（リソース名・プロジェクト名は自分の環境のものに置き換える）：
```bash
az cognitiveservices account project show \
  --name <project-name> --resource-group <resource-group> \
  --query 'properties.endpoints."AI Foundry API"' -o tsv
```

`.env` を編集して `PROJECT_ENDPOINT` と `MODEL_DEPLOYMENT`（自分の環境の実際のデプロイ名）を書き込んだら：
```bash
python main.py
```

**取り込み（ベクトル化）には数秒〜十数秒かかります。** `python main.py` を実行してもすぐには何も表示されないことがありますが、正常です。

質問を変えたいときは、実行前に環境変数で上書きできます：
```bash
# PowerShell
$env:QUESTION = "この製品の重さは？"
python main.py
```
```bash
# bash
QUESTION="この製品の重さは？" python main.py
```

## 期待される出力（例）
```
ベクトルストア作成・取り込み完了 (id: vs_...)

=== 回答 ===
この製品の保証期間は1年間で、対応OSはWindows 11およびmacOS 13以降です。...

後片付け完了（エージェント・ベクトルストアを削除）
```
文書にない内容（例：「この製品の重さは？」）を聞くと、モデルは一般論で埋めずに「文書に記載がありません」という趣旨の答えを返します（実行するたびに文言は変わります）。

## ポイント（試験の論点）
- **引用は本文とは別の場所に入る**：File Search の出典情報は `response.output` 内の `file_search_call` や `message` の `annotations`（`file_citation`）に入る。回答本文に「【…】」や「出典：…」のような印が自動で付くわけではない。
- **チャンク化は既定値がある**（`upload_and_poll` は `chunking_strategy` で `max_chunk_size_tokens`・`chunk_overlap_tokens` を指定でき、既定は800/400）。
- **実行後もアップロードした文書ファイル自体は Files に残る**（`finally` で削除するのはエージェントとベクトルストアのみ）。不要なら別途 `openai.files.delete(...)` で消す。

## つまずきポイント
| 症状 | 対処 |
|---|---|
| `model not found` | `MODEL_DEPLOYMENT` が**デプロイ名**と一致しているか（カタログ名ではない） |
| `401`/`403` | `az login` 済みか、プロジェクトに **Foundry User** ロールがあるか |
| 取り込みが終わらない | 文書サイズやネットワークによって数秒〜1分程度かかることがある。気長に待つ |
| ファイルが見つからない | `DOC_PATH`（既定 `product_info.md`）が実行時のカレントディレクトリから見えているか |

## 後片付け（課金回避）
- `main.py` は `finally` で**エージェントとベクトルストアを毎回自動削除**する。異常終了（`Ctrl+C` など）した場合は、手動で削除するか、次の確認コマンドで残骸を確認できる：
```bash
python -c "import os;from dotenv import load_dotenv;load_dotenv();from azure.identity import DefaultAzureCredential as C;from azure.ai.projects import AIProjectClient as P;p=P(endpoint=os.environ['PROJECT_ENDPOINT'],credential=C());o=p.get_openai_client();print('vector_stores:',[(v.id,v.name) for v in o.vector_stores.list()]);print('files:',[(f.id,f.filename) for f in o.files.list()]);print('agents:',[a.name for a in p.agents.list()])"
```
