"""
aucfan_scraper.py
aucfan.com からメルカリの90日間価格データを取得するモジュール
Playwright（同期版）を使用
"""

import re
import time
from datetime import datetime
from playwright.sync_api import sync_playwright


def get_date_param() -> str:
    """
    現在日付から90日前の期間パラメータを生成
    形式: t-YYYYMMYYYYMM (終了年月・開始年月)
    """
    now = datetime.now()
    end_year = now.year
    end_month = now.month

    # 3ヶ月前を計算
    start_month = end_month - 3
    start_year = end_year
    if start_month <= 0:
        start_month += 12
        start_year -= 1

    return f"t-{end_year:04d}{end_month:02d}{start_year:04d}{start_month:02d}"


def encode_keyword(keyword: str) -> str:
    """aucfan用キーワードエンコード"""
    return keyword.replace(' ', '.20').replace('-', '.2d')


def extract_prices_from_page(page, model: str) -> list[int]:
    """
    aucfanページから価格リストを抽出するJavaScript実行
    モデル名を使った簡易フィルタ付き
    """
    # モデル名から除外キーワード・フィルタキーワードを生成
    model_upper = model.upper()

    js_code = """
    () => {
        const text = document.body.innerText;
        const lines = text.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
        const items = [];

        for (let i = 0; i < lines.length; i++) {
            const m = lines[i].match(/^([0-9,]+)円$/);
            if (m) {
                const price = parseInt(m[1].replace(/,/g, ''));
                if (price < 500 || price > 300000) continue;

                let title = '';
                for (let j = i - 1; j >= Math.max(0, i - 8); j--) {
                    const l = lines[j];
                    if (
                        l.length > 8 &&
                        !l.includes('出品者') &&
                        !l.includes('メルカリ') &&
                        !l.includes('商品状態') &&
                        !/^[0-9,]+円/.test(l) &&
                        !l.includes('件')
                    ) {
                        title = l.substring(0, 100);
                        break;
                    }
                }
                items.push({ price, title });
            }
        }
        return items;
    }
    """

    items = page.evaluate(js_code)

    # アクセサリ除外フィルタ
    accessory_keywords = ['互換', 'バッテリー', '充電器', 'ケーブル', 'NP-', 'BLS-', 'LI-', 'EN-EL',
                          'レンズキャップ', 'ストラップのみ', '説明書のみ']

    filtered = []
    for item in items:
        title = item['title'].upper()
        price = item['price']

        # アクセサリ除外
        is_accessory = any(kw.upper() in title for kw in accessory_keywords)
        if is_accessory:
            continue

        filtered.append(price)

    return sorted(filtered)


def get_mercari_stats(maker: str, model: str, progress_callback=None) -> dict:
    """
    メーカー・型番でaucfanを検索し、メルカリ90日間統計を返す

    Returns:
        {
            "count": 件数,
            "median": 中央値,
            "max": 最高値,
            "min": 最低値,
            "url": 検索URL
        }
    """
    keyword = f"{maker} {model}"
    encoded = encode_keyword(keyword)
    date_param = get_date_param()
    url = f"https://aucfan.com/search1/q-{encoded}/s-mc/{date_param}/?o=de"

    result = {
        "count": 0,
        "median": None,
        "max": None,
        "min": None,
        "url": url,
        "error": None,
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # タイムアウト設定
            page.set_default_timeout(15000)

            page.goto(url)

            # SPA読み込み待機（最大5秒）
            try:
                page.wait_for_function(
                    "document.body.innerText.length > 3000",
                    timeout=5000
                )
            except Exception:
                pass  # タイムアウトしても続行

            # 価格抽出
            prices = extract_prices_from_page(page, model)
            browser.close()

        if not prices:
            return result

        n = len(prices)
        if n % 2 == 1:
            median = prices[n // 2]
        else:
            median = round((prices[n // 2 - 1] + prices[n // 2]) / 2)

        result.update({
            "count": n,
            "median": median,
            "max": max(prices),
            "min": min(prices),
        })

    except Exception as e:
        result["error"] = str(e)

    return result


def batch_search(cameras: list[dict], progress_callback=None) -> list[dict]:
    """
    複数カメラをまとめて検索

    Args:
        cameras: [{"maker": "CANON", "model": "EOS Kiss X9", "price_tax_in": 55000}, ...]
        progress_callback: 進捗コールバック関数 (current, total, camera_name) -> None

    Returns:
        検索結果を追加したリスト
    """
    results = []
    total = len(cameras)

    for i, cam in enumerate(cameras):
        if progress_callback:
            progress_callback(i, total, f"{cam['maker']} {cam['model']}")

        stats = get_mercari_stats(cam['maker'], cam['model'])

        results.append({
            "メーカー": cam.get("maker", ""),
            "型番": cam.get("model", ""),
            "仕入価格(税込)": cam.get("price_tax_in", 0),
            "件数": stats["count"],
            "中央値": stats["median"],
            "最高値": stats["max"],
            "最低値": stats["min"],
            "aucfan URL": stats["url"],
            "エラー": stats.get("error", ""),
        })

        # サーバー負荷軽減のため1秒待機
        if i < total - 1:
            time.sleep(1)

    if progress_callback:
        progress_callback(total, total, "完了")

    return results
