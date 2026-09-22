# L1-5 実践: キーレス化（DefaultAzureCredential ＋ ロール割り当て）

**APIキーを使わず**、Microsoft Entra ID（`az login`／マネージドID）のトークンで Foundry を呼び、
**ロール割り当て**と **local auth 無効化（`disableLocalAuth`）** までやってキーレスを仕上げるハンズオンです。

> 対応レクチャー：座学 `L1-5-1`(キーレス・マネージドID)／`L1-5-2`(RBAC・Key Vault)／`L1-5-3`(ネットワーク分離)、実践 `L1-5-4` ／ 対応スキル：S1.c-4
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。キー方式は「無効化されることを確認する」ためだけに登場します。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | **Foundry プロジェクト**を `AIProjectClient` + `DefaultAzureCredential` でキーレス呼び出し（Responses API） |
| `keyless_openai_direct.py` | **OpenAI SDK + トークンプロバイダー**でモデル直接呼び出し。キー方式との対比 |
| `assign_role_disable_key.azcli` | **ロール確認・割り当て** ＋ **スコープ違いトークンの 401 確認** ＋ **local auth 無効化** ＋ **キー再生成** |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- Foundry プロジェクト作成済み・チャットモデルを1つデプロイ済み（例 `gpt-5.4`）
- ロール割り当て・`disableLocalAuth` 操作には **Owner / User Access Administrator** 等の権限

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集してから:

# 1) いま自分に何のロールが付いているかを確認（azcli の 0）
# 2) キーレスで呼べることを確認
python main.py
python keyless_openai_direct.py
# 3) ロール割り当ての実演（azcli の 1〜3）／スコープ違いトークンで 401（azcli の 4）
# 4) local auth を無効化（azcli の 5）してキー方式が 403 になることを確認
# 5) キーを再生成して失効させる（azcli の 6）
```

## 必要なロール（ここが試験の論点）
| 呼び方 | 必要なロール | スコープ |
|---|---|---|
| `main.py`（プロジェクト経由） | **Foundry User**（旧 Azure AI User、GUID `53ca6127-db72-4b80-b1b0-d745d6d5456d`） | プロジェクト／アカウント（上位からの継承も可） |
| `keyless_openai_direct.py`（リソース直接） | **Cognitive Services User**（アカウントスコープの **Foundry User** でも可） | Foundry アカウント |

- ⚠️ **`Owner` / `Contributor` では推論できません。** これらは**コントロールプレーン**のロールで、データアクションを持ちません。
- ⚠️ **`Cognitive Services OpenAI User` は OpenAI モデルだけ**に効きます。Foundry の他モデルには届きません。
- ⚠️ **ロールは上位スコープから継承されます。** サブスクリプションやリソースグループに `Foundry User` が付いていれば、リソース／プロジェクトに何も付けなくても呼べます。「なぜ動くのか」も `az role assignment list` で確認してください。
- ⚠️ **反映は即時ではありません。** 公式ガイダンスは「最初の呼び出しまで **5分以上待つ**」です。

## 期待される出力（例）
`main.py`：
```
✅ キーレスで接続: https://xxx.services.ai.azure.com/api/projects/yyy
----- モデル応答 -----
キーレス認証は、鍵を共有せず ID にロールを割り当てて最小権限で安全にアクセスできる点が利点です。
```

`assign_role_disable_key.azcli` の 4（スコープ違いトークン）：
```
401     ← ARM 用トークン（宛先が違う）
200     ← Foundry 用トークン（https://ai.azure.com/.default）
```

## つまずき
- **`403 Forbidden` / `401 PermissionDenied`**：ロール不足。上の表のロールを割り当て、**5分以上待って**再実行。`Owner` だけでは通りません。
- **`401 Unauthorized`（`audience is incorrect`）**：トークンの**宛先違い**。スコープは `https://ai.azure.com/.default`。`az login` していない場合もここ。
- **`disableLocalAuth` 後にキー方式が 403**：期待どおりの動作です。`AuthenticationTypeDisabled`（`Key based authentication is disabled for this resource.`）が返ります。反映は収録環境では即時でしたが、公式ドキュメントは「通常数分、最大で数時間」としています。まだ 200 が返る場合は少し待って再実行してください。
- **`Custom subdomain required`**：リソースにカスタムサブドメインが無い。トークン認証の前提条件です。
- **`404 Workspace not found`**：`PROJECT_ENDPOINT` のプロジェクトが存在しない（削除済み等）。ポータルで現行のエンドポイントを確認。
- **`model not found`**：`MODEL_DEPLOYMENT` は**カタログ名ではなくデプロイ名**。
- ロール改称のロールアウト中なので、CLI では **Foundry User を GUID `53ca6127-...` で指定**するのが安全です。

## 後片付け
- ロール割り当て・キー無効化は**無料**。推論を数回するだけなので、リソースグループを削除する必要はありません（後続レッスンでも同じリソースを使います）。
- `disableLocalAuth` を戻す：`az resource update --ids $FOUNDRY_ID --set properties.disableLocalAuth=false`
- 割り当てたロールを外す：`az role assignment delete ...`（azcli の後片付けセクション参照）
