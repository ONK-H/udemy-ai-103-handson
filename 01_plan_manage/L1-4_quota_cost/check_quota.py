"""L1-4 実践(1/3): クォータ消費と利用可能容量をプログラムで確認する。

Azure Resource Manager(ARM) の 3 つの REST API を、キーレス認証
(DefaultAzureCredential / az login 済みの資格情報) で呼び出す。

- quotaTiers API      : サブスクリプションのクォータティア(等級)。「そもそも割り当てが付くモデルか」の土台
- Usages API          : サブスク×リージョンの全クォータ行 (現在使用量 currentValue / 上限 limit)
- Model Capacities API: あるモデルを「どこに・どれだけデプロイできるか」(デプロイ前の事前チェック)

必要ロール: クォータ閲覧は「Cognitive Services Usages Reader」(サブスクリプションスコープ) が最小権限。
"""
import os

import requests
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")
LOCATION = os.getenv("QUOTA_LOCATION", "eastus")
API_VERSION = "2024-10-01"  # ※収録時に最新の api-version を確認
TIERS_API_VERSION = "2025-10-01-preview"  # quotaTiers は執筆時点でプレビュー

# Model Capacities API 用 (任意)
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5.4")
MODEL_VERSION = os.getenv("MODEL_VERSION", "2026-03-05")
MODEL_FORMAT = os.getenv("MODEL_FORMAT", "OpenAI")

ARM = "https://management.azure.com"

# ARM 用のアクセストークンを取得 (キーは使わない)
credential = DefaultAzureCredential()
token = credential.get_token("https://management.azure.com/.default")
HEADERS = {"Authorization": f"Bearer {token.token}"}


def show_quota_tier():
    """quotaTiers API: サブスクリプションのクォータティア(等級)を表示。

    ティアの表に載っているモデルにしか既定クォータが付かないため、
    「カタログにあるのにデプロイできない (insufficient quota)」の切り分けは、まずここを見る。
    最下位ティア(Free Tier / Tier 0)で割り当てが付くのは 4 モデルだけ。
    """
    url = (
        f"{ARM}/subscriptions/{SUBSCRIPTION_ID}"
        f"/providers/Microsoft.CognitiveServices/quotaTiers"
        f"?api-version={TIERS_API_VERSION}"
    )
    print("\n===== クォータティア (このサブスクリプションの等級) =====")
    try:
        res = requests.get(url, headers=HEADERS, timeout=30)
        res.raise_for_status()
    except requests.HTTPError as ex:
        # プレビュー API なので、未提供リージョン/権限不足でも後続を止めない
        print(f"(ティアを取得できませんでした: {ex})")
        return

    for item in res.json().get("value", []):
        props = item.get("properties", {})
        print(f"現在のティア: {props.get('currentTierName', '不明')}")
        print(f"割り当て日   : {props.get('assignmentDate', '-')}")
        print(f"昇格ポリシー : {props.get('tierUpgradePolicy', '-')}")


def list_usages():
    """Usages API: 指定リージョンのクォータ消費を一覧表示 (limit > 0 の行のみ)。"""
    url = (
        f"{ARM}/subscriptions/{SUBSCRIPTION_ID}"
        f"/providers/Microsoft.CognitiveServices/locations/{LOCATION}/usages"
        f"?api-version={API_VERSION}"
    )
    res = requests.get(url, headers=HEADERS, timeout=30)
    res.raise_for_status()
    usages = res.json().get("value", [])

    print(f"\n===== クォータ消費 / 上限 ({LOCATION}) =====")
    shown = 0
    for item in usages:
        if item.get("limit", 0) > 0:
            name = item["name"]["localizedValue"]  # 例: "Tokens Per Minute (thousands) - gpt-5.4"
            print(f"{name}: {item['currentValue']}/{item['limit']}")
            shown += 1
    if shown == 0:
        print("(limit > 0 のクォータ行がありません。リージョン/サブスクを確認してください)")


def list_model_capacities():
    """Model Capacities API: あるモデルを Standard でデプロイできる空き容量をリージョン別に表示。"""
    url = (
        f"{ARM}/subscriptions/{SUBSCRIPTION_ID}"
        f"/providers/Microsoft.CognitiveServices/modelCapacities"
        f"?api-version={API_VERSION}"
        f"&modelFormat={MODEL_FORMAT}&modelName={MODEL_NAME}&modelVersion={MODEL_VERSION}"
    )
    res = requests.get(url, headers=HEADERS, timeout=30)
    res.raise_for_status()
    capacities = res.json().get("value", [])

    print(f"\n===== {MODEL_NAME} ({MODEL_VERSION}) の Standard 系 空き容量 =====")
    shown = 0
    for item in capacities:
        props = item.get("properties", {})
        if props.get("availableCapacity", 0) > 0 and "Standard" in props.get("skuName", ""):
            print(f"{item['location']} ({props['skuName']}): {props['availableCapacity']} 利用可能")
            shown += 1
    if shown == 0:
        print("(空き容量のある Standard デプロイ先が見つかりませんでした)")


def main():
    if not SUBSCRIPTION_ID:
        print("AZURE_SUBSCRIPTION_ID が未設定です。.env を確認してください。")
        return
    try:
        show_quota_tier()
        list_usages()
        list_model_capacities()
    except requests.HTTPError as ex:
        # 403 ならロール不足 (Cognitive Services Usages Reader をサブスクスコープで付与)
        # ※ requests.Response は 4xx/5xx のとき bool() が False になるので `is not None` で判定する
        print(f"HTTP エラー: {ex} / 応答: {ex.response.text if ex.response is not None else ''}")
    except Exception as ex:
        print(f"エラー: {ex}")


if __name__ == "__main__":
    main()
