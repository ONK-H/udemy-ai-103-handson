"""L5-1 実践(1/2): スキルセットでエンリッチした AI Search インデックスを作る。

Text Split（チャンク化）+ Azure OpenAI Embedding（ベクトル化）= integrated vectorization。
データソース／インデックス／スキルセット／インデクサーの4オブジェクトをコードで作成・実行する。
認証はキーレス（az login + DefaultAzureCredential）。
"""

import os
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
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
# model_name はカタログのモデル名（text-embedding-3-large など）。デプロイ名と同じなら省略可
EMB_MODEL = os.getenv("AOAI_EMBEDDING_MODEL", EMB_DEPLOY)
DIMS = int(os.getenv("AOAI_EMBEDDING_DIMENSIONS", "3072"))


def build() -> None:
    # 1) インデックス（ベクトル＋引用用フィールド）。クエリ時 vectorizer も定義する
    index_client = SearchIndexClient(SEARCH_ENDPOINT, cred)
    index = SearchIndex(
        name=INDEX,
        fields=[
            # index projections のキーは Edm.String + keyword アナライザーが条件（公式の要件）
            SearchableField(name="chunk_id", type=SearchFieldDataType.String, key=True,
                            sortable=True, filterable=True, analyzer_name="keyword"),
            SimpleField(name="parent_id", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),  # 引用用
            SearchField(name="content_vector",
                        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                        searchable=True, vector_search_dimensions=DIMS,
                        vector_search_profile_name="vprofile"),
        ],
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
            profiles=[VectorSearchProfile(name="vprofile",
                                          algorithm_configuration_name="hnsw",
                                          vectorizer_name="aoai-vectorizer")],
            vectorizers=[AzureOpenAIVectorizer(
                vectorizer_name="aoai-vectorizer",
                parameters=AzureOpenAIVectorizerParameters(
                    resource_url=AOAI_ENDPOINT, deployment_name=EMB_DEPLOY,
                    model_name=EMB_MODEL),
            )],
        ),
        # セマンティック構成：エージェント側の既定 query_type（vector_semantic_hybrid）が使う
        semantic_search=SemanticSearch(
            default_configuration_name="default",
            configurations=[SemanticConfiguration(
                name="default",
                prioritized_fields=SemanticPrioritizedFields(
                    content_fields=[SemanticField(field_name="content")]),
            )],
        ),
    )
    index_client.create_or_update_index(index)
    print(f"index ready: {INDEX}")

    ixr = SearchIndexerClient(SEARCH_ENDPOINT, cred)

    # 2) データソース（Blob・マネージドID）
    ds = SearchIndexerDataSourceConnection(
        name=f"{INDEX}-ds", type="azureblob",
        connection_string=os.environ["BLOB_CONNECTION_STRING"],
        container=SearchIndexerDataContainer(name=os.environ["BLOB_CONTAINER"]),
    )
    ixr.create_or_update_data_source_connection(ds)
    print(f"data source ready: {ds.name}")

    # 3) スキルセット：Text Split（チャンク化）→ Azure OpenAI Embedding（ベクトル化）
    skillset = SearchIndexerSkillset(
        name=f"{INDEX}-ss",
        description="integrated vectorization: split + embed",
        skills=[
            SplitSkill(
                text_split_mode="pages", maximum_page_length=2000, page_overlap_length=200,
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
        # チャンクごとに1インデックスドキュメントを作る（index projections）
        index_projection=SearchIndexerIndexProjection(
            selectors=[SearchIndexerIndexProjectionSelector(
                target_index_name=INDEX, parent_key_field_name="parent_id",
                source_context="/document/pages/*",
                mappings=[
                    InputFieldMappingEntry(name="content", source="/document/pages/*"),
                    InputFieldMappingEntry(name="content_vector",
                                           source="/document/pages/*/content_vector"),
                    InputFieldMappingEntry(name="source",
                                           source="/document/metadata_storage_name"),
                ],
            )],
            parameters=SearchIndexerIndexProjectionsParameters(
                projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS),
        ),
    )
    ixr.create_or_update_skillset(skillset)
    print(f"skillset ready: {skillset.name}")

    # 4) インデクサー：データソース→スキルセット→インデックス を駆動
    indexer = SearchIndexer(
        name=f"{INDEX}-idxr", data_source_name=ds.name, skillset_name=skillset.name,
        target_index_name=INDEX,
    )
    ixr.create_or_update_indexer(indexer)   # 新規作成時はこの時点で自動的に1回走る
    try:
        ixr.run_indexer(indexer.name)
    except HttpResponseError as e:
        # 作成・更新時の自動実行と重なると「Another indexer invocation is currently in progress」
        if e.status_code != 409 and "in progress" not in str(e):
            raise
        print("indexer は作成時の自動実行中です（同時実行エラーは想定内）。")
    print("indexer started. 数分後に Foundry/ポータルでドキュメント件数を確認してください。")


if __name__ == "__main__":
    try:
        build()
    except Exception as e:  # 教育目的のエラーハンドリング
        print(f"エラー: {type(e).__name__}: {e}")
        print("RBAC（Search Service Contributor / Search Index Data Contributor / "
              "Cognitive Services OpenAI User / Storage Blob Data Reader）と "
              ".env の値を確認してください。")
        raise
