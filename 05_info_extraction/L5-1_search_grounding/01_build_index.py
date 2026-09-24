"""L5-1 実践(1/3): スキルセットでエンリッチした AI Search インデックスを作る。

統合ベクトル化 = 取り込み時の Text Split + Azure OpenAI Embedding と、クエリ時の vectorizer の両方を Search に任せること。
データソース → スキルセット → インデックス → インデクサーの4つをコードで作り、取り込みの完了を待つ。
認証はキーレス（az login + DefaultAzureCredential、検索サービスのマネージド ID）。

使い方:
    python 01_build_index.py            # 作る → 取り込み完了を待つ → チャンク数を表示
    python 01_build_index.py --delete   # 4つのオブジェクトを消す（後片付け）
"""

import os
import sys
import time

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType, SimpleField, SearchableField,
    VectorSearch, HnswAlgorithmConfiguration, VectorSearchProfile,
    AzureOpenAIVectorizer, AzureOpenAIVectorizerParameters,
    SearchIndexerDataSourceConnection, SearchIndexerDataContainer,
    SearchIndexerSkillset, SplitSkill, AzureOpenAIEmbeddingSkill,
    InputFieldMappingEntry, OutputFieldMappingEntry,
    SearchIndexerIndexProjection, SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters, IndexProjectionMode,
    SearchIndexer,
    SemanticSearch, SemanticConfiguration, SemanticPrioritizedFields, SemanticField,
)
from dotenv import load_dotenv

load_dotenv()
cred = DefaultAzureCredential()

SEARCH_ENDPOINT = os.environ["SEARCH_ENDPOINT"]
INDEX = os.environ["SEARCH_INDEX_NAME"]
AOAI_ENDPOINT = os.environ["AOAI_ENDPOINT"]
EMB_DEPLOY = os.environ["AOAI_EMBEDDING_DEPLOYMENT"]
# model_name はカタログのモデル名。デプロイ名と同じなら省略可
EMB_MODEL = os.getenv("AOAI_EMBEDDING_MODEL", EMB_DEPLOY)
DIMS = int(os.getenv("AOAI_EMBEDDING_DIMENSIONS", "3072"))
DS, SS, IDXR = f"{INDEX}-ds", f"{INDEX}-ss", f"{INDEX}-idxr"


def build() -> None:
    # 1) インデックス：チャンク本文・ベクトル・引用用の title/url。クエリ時のベクトル化（vectorizer）も定義する
    index = SearchIndex(
        name=INDEX,
        fields=[
            # index projections のキーは Edm.String ＋ keyword アナライザーが条件
            SearchableField(name="chunk_id", type=SearchFieldDataType.String, key=True,
                            sortable=True, filterable=True, analyzer_name="keyword"),
            SimpleField(name="parent_id", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="content", type=SearchFieldDataType.String,
                            analyzer_name="ja.microsoft"),  # 日本語の単語区切りでキーワード検索する
            SimpleField(name="title", type=SearchFieldDataType.String, filterable=True),  # 引用の名前
            SimpleField(name="url", type=SearchFieldDataType.String),                     # 引用のリンク
            SearchField(name="content_vector",
                        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                        searchable=True, vector_search_dimensions=DIMS,
                        vector_search_profile_name="vprofile"),
        ],
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
            profiles=[VectorSearchProfile(name="vprofile", algorithm_configuration_name="hnsw",
                                          vectorizer_name="aoai-vectorizer")],
            vectorizers=[AzureOpenAIVectorizer(
                vectorizer_name="aoai-vectorizer",
                parameters=AzureOpenAIVectorizerParameters(
                    resource_url=AOAI_ENDPOINT, deployment_name=EMB_DEPLOY, model_name=EMB_MODEL),
            )],
        ),
        # セマンティック構成：エージェントの既定の query_type（vector_semantic_hybrid）が使う
        semantic_search=SemanticSearch(
            default_configuration_name="default",
            configurations=[SemanticConfiguration(
                name="default",
                prioritized_fields=SemanticPrioritizedFields(
                    content_fields=[SemanticField(field_name="content")]),
            )],
        ),
    )
    SearchIndexClient(SEARCH_ENDPOINT, cred).create_or_update_index(index)
    print(f"① インデックス  {INDEX}")

    ixr = SearchIndexerClient(SEARCH_ENDPOINT, cred)

    # 2) データソース：Blob を「ResourceId=…」で指す＝検索サービスのマネージド ID で読む（キー不要）
    ds = SearchIndexerDataSourceConnection(
        name=DS, type="azureblob",
        connection_string=f"ResourceId={os.environ['STORAGE_RESOURCE_ID']};",
        container=SearchIndexerDataContainer(name=os.environ["BLOB_CONTAINER"]),
    )
    ixr.create_or_update_data_source_connection(ds)
    print(f"② データソース  {DS}（コンテナー {os.environ['BLOB_CONTAINER']}）")

    # 3) スキルセット：Text Split（チャンク化）→ Azure OpenAI Embedding（ベクトル化）
    skillset = SearchIndexerSkillset(
        name=SS,
        description="integrated vectorization: split + embed",
        skills=[
            SplitSkill(
                text_split_mode="pages", maximum_page_length=300, page_overlap_length=30,
                context="/document",
                inputs=[InputFieldMappingEntry(name="text", source="/document/content")],
                outputs=[OutputFieldMappingEntry(name="textItems", target_name="pages")],
            ),
            AzureOpenAIEmbeddingSkill(
                context="/document/pages/*",
                resource_url=AOAI_ENDPOINT, deployment_name=EMB_DEPLOY,
                model_name=EMB_MODEL, dimensions=DIMS,
                inputs=[InputFieldMappingEntry(name="text", source="/document/pages/*")],
                outputs=[OutputFieldMappingEntry(name="embedding", target_name="content_vector")],
            ),
        ],
        # チャンク1つを、インデックスの1ドキュメントにする（index projections）
        index_projection=SearchIndexerIndexProjection(
            selectors=[SearchIndexerIndexProjectionSelector(
                target_index_name=INDEX, parent_key_field_name="parent_id",
                source_context="/document/pages/*",
                mappings=[
                    InputFieldMappingEntry(name="content", source="/document/pages/*"),
                    InputFieldMappingEntry(name="content_vector",
                                           source="/document/pages/*/content_vector"),
                    InputFieldMappingEntry(name="title", source="/document/metadata_storage_name"),
                    InputFieldMappingEntry(name="url", source="/document/metadata_storage_path"),
                ],
            )],
            parameters=SearchIndexerIndexProjectionsParameters(
                projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS),
        ),
    )
    ixr.create_or_update_skillset(skillset)
    print(f"③ スキルセット  {SS}（Text Split 300字・重なり30字 → Embedding {DIMS}次元）")

    # 4) インデクサー：データソース → スキルセット → インデックスを動かす（作成と同時に1回走る）
    ixr.create_or_update_indexer(SearchIndexer(
        name=IDXR, data_source_name=DS, skillset_name=SS, target_index_name=INDEX))
    print(f"④ インデクサー  {IDXR}")

    # 取り込みの完了を 10 秒おきに待つ
    for _ in range(60):
        time.sleep(10)
        last = ixr.get_indexer_status(IDXR).last_result
        if last and last.status in ("success", "transientFailure", "persistentFailure"):
            break
    print(f"⑤ 取り込み      {getattr(last.status, 'value', last.status)}：処理 {last.item_count} 件 / 失敗 {last.failed_item_count} 件")
    for err in (last.errors or [])[:2]:
        print(f"   エラー: {err.error_message[:150]}")

    time.sleep(3)  # 件数の反映待ち
    n = SearchClient(SEARCH_ENDPOINT, INDEX, cred).get_document_count()
    print(f"⑥ インデックスのドキュメント数（＝チャンク数） {n}")


def delete() -> None:
    ixr = SearchIndexerClient(SEARCH_ENDPOINT, cred)
    for kind, fn in (("インデクサー", lambda: ixr.delete_indexer(IDXR)),
                     ("スキルセット", lambda: ixr.delete_skillset(SS)),
                     ("データソース", lambda: ixr.delete_data_source_connection(DS)),
                     ("インデックス", lambda: SearchIndexClient(SEARCH_ENDPOINT, cred).delete_index(INDEX))):
        try:
            fn()
            print(f"削除: {kind}")
        except ResourceNotFoundError:
            print(f"なし: {kind}")


if __name__ == "__main__":
    try:
        delete() if "--delete" in sys.argv else build()
    except HttpResponseError as e:
        print(f"エラー: {e.status_code} {str(e.message).splitlines()[0][:160]}")
        print("ロール（手順5）と .env の値を確認してください。付けた直後なら数分待って再実行します。")
        sys.exit(1)
