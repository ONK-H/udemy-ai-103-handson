# L1-1 実践: 2モデル（大／小）を同一タスクで比較する

同じプロンプトを **「大きいモデル」と「小さいモデル」** に投げ、**出力・レイテンシ・トークン数（≒コスト）** を並べて比較する CLI です。座学で学ぶ「精度／レイテンシ／コストはトレードオフ」を自分の目で確かめるのが狙いです。

> 対応レクチャー：座学 `L1-1-1`（Foundry のモデル地図）／`L1-1-2`（モデル選択）、実践 `L1-1-3` ／ 対応スキル：S1.a-1
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。APIキーは使いません。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | 2モデルに同一プロンプトを投げ、レイテンシ／入出力トークン／本文を並べて表示 |
| `.env.sample` | 環境変数の雛形（エンドポイントと比較する2モデル名） |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- Microsoft Foundry プロジェクト作成済み（L0-3）。プロジェクトエンドポイントを控えておく
- **比較する2モデルをデプロイ済み**（既定は `gpt-5.4` と `gpt-5.4-nano`）
- ロール：プロジェクトに **Foundry User**（旧 Azure AI User）相当

## 進め方（PowerShell）
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1     # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env            # macOS/Linux: cp .env.sample .env
# .env を編集してから:

python main.py
```

## 期待される出力（例）
```
===== 大 (LARGE): gpt-5.4 =====
レイテンシ: 1.83s / 入力トークン: 31 / 出力トークン: 96
出力:
Microsoft Foundry は… （3文の説明）

===== 小 (SMALL): gpt-5.4-nano =====
レイテンシ: 0.92s / 入力トークン: 31 / 出力トークン: 88
出力:
Microsoft Foundry は… （3文の説明）
```
数値はリージョン・混雑で変動します。**傾向**（小さいモデルの方が速く・安い）が見えればOKです。

## クォータ不足でモデルをデプロイできないとき

Foundry ポータルでデプロイしようとして **`gpt-5.4 isn't available due to insufficient quota`** と出る場合、設定ミスではありません。**そのサブスクリプションに、そのモデルの割り当てが1つも無い**状態です。

Foundry はサブスクリプションごとに **クォータティア**（最下位＝Free Tier / Tier 0 〜 Tier 6）を割り当てており、**ティアの表に載っているモデルにしか既定クォータが付きません**。初期ティアは利用実績と Microsoft との契約関係で決まるため、**作りたてのサブスクリプションは最下位ティアになりやすい**です。

現在のティアの確認（ポータルには表示がないため API で確認します）：

```powershell
az rest --method get `
  --url "https://management.azure.com/subscriptions/$(az account show --query id -o tsv)/providers/Microsoft.CognitiveServices/quotaTiers?api-version=2025-10-01-preview"
```

**最下位ティアで既定クォータが付与されるのは次の4モデルだけ**です（すべて GlobalStandard）。

| モデル | 既定クォータ |
|---|---|
| `gpt-4.1-mini` | 200,000 TPM |
| `gpt-5-mini` | 500,000 TPM |
| `o4-mini` | 100,000 TPM |
| `text-embedding-3-small` | 1,000,000 TPM |

### 対処1：使えるモデルに差し替える（推奨）
`.env` を次のように変更すれば、このハンズオンは**そのまま実施できます**。

```
MODEL_LARGE=gpt-5-mini      # 推論モデル。思考トークンを出すので遅く・消費が多い＝「大きい側」
MODEL_SMALL=gpt-4.1-mini    # 非推論モデル。速く・安い＝「小さい側」
```

推論モデル対非推論モデルになるため、**レイテンシとトークン数の差はむしろはっきり出ます**。
※ `gpt-4.1-mini` はライフサイクルが Legacy（廃止予定 2027-04-14。2026-09-19 確認）です。実行時点の廃止スケジュールを確認してください。

### 対処2：クォータ増加を申請する
[クォータ増加申請フォーム](https://aka.ms/oai/stuquotarequest) から、**サブスクリプション・リージョン・モデル名・希望 TPM** を明記して申請します（サブスクリプションの **Owner** または **Contributor** が必要）。承認されてもティアは変わらず、割り当てだけ増えます。反映まで最大15分。
> 申請は「**既存クォータを実際に使っている顧客が優先**」されます。まず対処1で実際に推論を回してから申請すると通りやすくなります。

### 対処3：待つ（自動昇格）
ティアは**消費実績と支払い履歴に応じて自動的に昇格**します。講座を進めるうちに上位モデルも使えるようになります。

### 効かない／注意が必要な回避策
| やろうとしがちなこと | 実際 |
|---|---|
| 別のリージョンでデプロイする | **効きません。** Global Standard のクォータは 2026年5月以降、サブスクリプション単位で**全リージョン共通の1プール**。ポータルの Quota 画面の **Scope 列**が `Global` / `Data Zone` ならこの新方式（リージョン名なら従来のリージョン別方式で、変更が効く可能性あり） |
| TPM（容量）を最小にして再試行 | 割り当てがゼロなら不可 |
| Data Zone Standard / Standard に切り替える | 別プールだが、最下位ティアには対象モデルの行が無いため不可 |
| Instant access（プレビュー）を使う | デプロイ不要だが**同じ per-model global quota を消費**し、**West US 3 のプロジェクト限定**。`gpt-5-mini` などは試せるが、割り当てゼロのモデルは同じく不可 |

## つまずきポイント
| 症状 | 対処 |
|---|---|
| `isn't available due to insufficient quota` | 上記「クォータ不足でモデルをデプロイできないとき」を参照 |
| `Quota exceeded`（割り当てはあるが空きなし） | Manage → Quota で他デプロイの TPM を減らして空きを作る（反映まで最大15分） |
| `DefaultAzureCredential` で認証エラー | `az login` 済みか、プロジェクトに **Foundry User** が付いているか確認 |
| `model not found` / 404 | `.env` のモデル名が**デプロイ名**と一致しているか（カタログ名ではなくデプロイ名） |
| `usage` が `None` | SDK／モデルにより戻り値の形が異なる。`getattr` で防御済み |
| 429（レート制限） | TPM/RPM 超過。少し待つ。詳細は L1-4 |
| エンドポイント形式エラー | `PROJECT_ENDPOINT` が `.../api/projects/<project>` 形式か確認 |

## 後片付け（課金回避）
- このハンズオンは**推論を数回**するだけ（数円程度）。デプロイを置いておくだけでは課金されません（従量課金の Standard 系）。
- 検証専用なら、リソースグループごと削除：`az group delete --name rg-ai103-handson`

## 注意（揮発情報）
- **モデルID・世代は更新が速い**。デプロイ前に Foundry のカタログで現行IDを確認してください。
- **ティア別 TPM 表はモデル追加のたびに変わります**（新しいモデルは上位ティアのみ、というケースあり）。→ https://learn.microsoft.com/azure/foundry/openai/quotas-limits#quota-tiers
- `quotaTiers` API は**プレビュー**（`2025-10-01-preview`）。
