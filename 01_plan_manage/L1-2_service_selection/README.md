# L1-2 サービス／検索・知識・メモリの選定（設計ワークショップ）

このレッスンは**コードを書かない設計回**です。Python の実行はありません。要件シナリオから「使う Foundry サービスの構成」を選び、**理由を言語化する**練習をします。実装（RAG・エージェント・Content Understanding）はセクション2/3/5 で行います。

## ファイル

| ファイル | 用途 |
|---|---|
| `scenario-worksheet.md` | **記入用**。7項目の表が空欄になっている。まずこれを自分で埋める |
| `scenario-worksheet-answers.md` | **モデル解答**。埋め終わってから答え合わせに使う |
| `images/scenarioA〜C.png` | 3シナリオの構成図（解答側で参照） |

## やること
1. `scenario-worksheet.md` を開く。
2. 3つのシナリオ（A: 社内QA ／ B: 文書要約 ／ C: マルチモーダル）について、7項目の選定表を**自分で埋める**。理由の欄を空けたまま先に進まない。
3. 各シナリオの**構成図**を描く（手描き・draw.io・PowerPoint など何でも可）。
4. `scenario-worksheet-answers.md` を開いて答え合わせをする。選定が違っていても、理由が要件に紐づいていればよい。
5. Foundry ポータル（https://ai.azure.com ）で講座共通のプロジェクト `ai103-project` を開き、**Build → Knowledge / Tools / Agents** で、選んだ部品の在り処を確認する（作成は不要）。接続（connection）は **Manage → Project details → Connected resources** にある。

## 必要なもの
- L0-3 で作った講座共通のプロジェクト `ai103-project`（ポータルで閲覧できればよい。新しいリソースの作成・課金は不要）
- `az login` は任意（ポータルを見るだけなら不要）

## 評価の観点
「正解は1つ」ではありません。**要件（権限・ソース数・クエリの複雑さ・GA縛り・モダリティ）に対して、選定理由を説明できるか**が大事です。

## 参考（座学 L1-2-1〜-3 の決定フロー）
1. グラウンディングの要否 → 2. 検索方式（keyword/vector/semantic/**hybrid**）→ 3. インデックス（integrated vectorization＋出典）→ 4. グラウンディング手段（AI Search 自作／File Search／**AI Search ツール**／**Foundry IQ**）→ 5. メモリ（会話／Memory store）→ 6. ツール（built-in／custom）→ 7. 認証（**Entra キーレス**）
