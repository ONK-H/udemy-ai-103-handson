# L2-8 実践: リモート MCP サーバーのツールをエージェントに接続する

**GitHub の MCP サーバー**（リモート）を `MCPTool` でエージェントに宣言し、ツール呼び出し前に**承認フロー**（`mcp_approval_request` → `mcp_approval_response`）を挟んで呼び出すハンズオンです。認証情報はコードに書かず、Foundry プロジェクトの**接続**に持たせます。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | `MCPTool` を宣言し、承認要求が来たら `y`/`N` を聞いて処理するエージェント |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 🔴 事前準備（コードの前に必要）
1. **GitHub の Personal Access Token（PAT）を作成**（最小権限・短い有効期限を推奨）。
2. **Foundry ポータルでプロジェクト接続を作成**：接続名は自由（例 `github-mcp`）、種類は **Key-based**、資格情報名 `Authorization`、値は `Bearer <PAT>`（`Bearer` の後ろに半角スペース）。
   - 導線例：ビルド → ツール → ツールに接続 → Custom → Model Context Protocol。または 管理 → プロジェクトの詳細 → 接続されているリソース。
3. 上記の**接続名**を `.env` の `MCP_CONNECTION_NAME` に入れる（PAT そのものはコードにもここにも書かない）。

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- Foundry プロジェクト作成済み・チャットモデルを1つデプロイ済み（`.env.sample` の既定 `gpt-5-mini` が無ければ、デプロイ済みのモデル名に読み替える。例 `gpt-5.4`）
- 上記「事前準備」の PAT・接続が作成済み

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集：PROJECT_ENDPOINT・MODEL_DEPLOYMENT（デプロイ名）・MCP_CONNECTION_NAME（事前準備で作った接続名）

python main.py
# [承認要求] server=github tool=get_me のようなメッセージが出たら y か N を入力
```

## 期待される出力（例）
```
エージェント作成: mcp-agent v1
[承認要求] server=github tool=get_me
このMCPツール呼び出しを承認しますか？ (y/N): y
AI> あなたの GitHub ユーザー名は ... です
エージェントを削除しました
```
`N` を選ぶとツールは実行されず、AI の応答は「確認できません」のような内容になります。

## つまずき
- **承認プロンプトが出ずにエラー**：`MCP_CONNECTION_NAME` の接続が存在しない、または種類が正しくない（Key-based で `Authorization: Bearer <PAT>` になっているか確認）。
- **`Unauthorized` / `Forbidden`**：PAT が失効・スコープ不足。接続の値を作り直す。
- **モデルが `MCPTool` を使わない**：`MODEL_DEPLOYMENT` が「MCP に対応」のモデルか確認（Foundry のツール対応表を参照。型番によっては MCP 非対応）。
- このコードは**1往復しか処理しません**。承認要求が2つ以上連続すると `AI>` が空になることがあります。

## 後片付け
- エージェントは `finally` で毎回削除されます（プロジェクトには残りません）。
- **撮影・検証後は PAT を GitHub 側で失効（Revoke）してください。** 接続 `github-mcp` は他レッスンで使わないなら削除して構いません。
