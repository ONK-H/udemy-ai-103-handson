"""L5-1 実践(2/3): 作ったインデックスを、エージェントを通さずに直接検索する。

同じ質問を「キーワード」「ベクトル」「ハイブリッド＋セマンティック」の3方式で投げ、
上位2件のチャンクを、点数と、チャンクに入っている見出しで並べる。
質問文のベクトル化はインデックスの vectorizer が行う（コード側で埋め込みを呼ばない）。

使い方:
    python 02_search_index.py
    python 02_search_index.py "雨の日に荷物を濡らさないには？"
"""

import os
import re
import sys

from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery
from dotenv import load_dotenv

load_dotenv()
client = SearchClient(os.environ["SEARCH_ENDPOINT"], os.environ["SEARCH_INDEX_NAME"],
                      DefaultAzureCredential())
q = sys.argv[1] if len(sys.argv) > 1 else "送料はいくら？"
vq = VectorizableTextQuery(text=q, k_nearest_neighbors=3, fields="content_vector")


def show(label: str, results, score_key: str) -> None:
    """上位2件のチャンクを、点数と「そのチャンクに入っている見出し」で表示する"""
    print(f"[{label}]")
    for r in list(results)[:2]:
        heads = re.findall(r"^## (.+)$", r["content"], flags=re.M) or ["（見出しの途中から）"]
        print(f"  {r[score_key]:.3f}  {' / '.join(heads)}")


try:
    print(f"質問: {q}")
    show("キーワード", client.search(search_text=q, top=2), "@search.score")
    show("ベクトル", client.search(search_text=None, vector_queries=[vq], top=2), "@search.score")
    show("ハイブリッド＋セマンティック",
         client.search(search_text=q, vector_queries=[vq], query_type="semantic",
                       semantic_configuration_name="default", top=2),
         "@search.reranker_score")
except HttpResponseError as e:
    print(f"エラー: {e.status_code} {str(e.message).splitlines()[0][:160]}")
    sys.exit(1)
