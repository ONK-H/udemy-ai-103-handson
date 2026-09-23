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
LOCATION = os.getenv("QUOTA_LOCATION", "japaneast")
API_VERSION = "2026-07-01"  # ※揮発情報。az provider show で現行の GA を確認する
TIERS_API_VERSION = "2025-10-01-preview"  # quotaTiers は執筆時点でプレビュー

# Model Capacities API 用 (任意)
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5.4")
MODEL_VERSION = os.getenv("MODEL_VERSION", "2026-03-05")
MODEL_FORMAT = os.getenv("MODEL_FORMAT", "OpenAI")

# 表示の絞り込み（行数が多いので、既定は MODEL_NAME の行だけ／空き容量は QUOTA_LOCATION の行だけ）
# 全件を見たいときは .env で USAGE_FILTER= と空にする／CAPACITY_ALL=1 にする
USAGE_FILTER = os.getenv("USAGE_FILTER", MODEL_NAME)
CAPACITY_ALL = os.getenv("CAPACITY_ALL", "0") == "1"

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
    rows = [u for u in usages if u.get("limit", 0) > 0]
    if USAGE_FILTER:
        # 名前は "... - gpt-5.4 - GlobalStandard" の形。" - " で区切った要素がモデル名と一致する行だけ
        rows = [u for u in rows if USAGE_FILTER in u["name"]["localizedValue"].split(" - ")]
        print(f"(モデル {USAGE_FILTER} の行だけ表示。全件は USAGE_FILTER を空にする)")
    for item in rows:
        name = item["name"]["localizedValue"]  # 例: "One Thousand Tokens Per Minute - gpt-5.4 - GlobalStandard"
        print(f"{name}: {item['currentValue']}/{item['limit']}")
    if not rows:
        print("(limit > 0 のクォータ行がありません。リージョン/サブスク/USAGE_FILTER を確認してください)")


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
    rows = [
        item for item in capacities
        if item.get("properties", {}).get("availableCapacity", 0) > 0
        and "Standard" in item.get("properties", {}).get("skuName", "")
    ]
    here = rows if CAPACITY_ALL else [i for i in rows if i["location"] == LOCATION]
    for item in here:
        props = item["properties"]
        print(f"{item['location']} ({props['skuName']}): {props['availableCapacity']} 利用可能")
    if not CAPACITY_ALL:
        print(f"(ほかに {len(rows) - len(here)} 件のデプロイ先に空きあり。全件は CAPACITY_ALL=1)")
    if not rows:
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
