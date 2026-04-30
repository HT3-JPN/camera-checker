"""
camera_ocr.py
写真からカメラ情報（メーカー・型番・税込価格）を抽出するモジュール
Claude APIのVision機能を使用
"""

import anthropic
import base64
import json
import re
from pathlib import Path


def encode_image(image_bytes: bytes) -> str:
    """画像をbase64エンコード"""
    return base64.standard_b64encode(image_bytes).decode("utf-8")


def extract_cameras_from_images(uploaded_files: list) -> list[dict]:
    """
    アップロードされた写真からカメラ情報を抽出する

    Args:
        uploaded_files: StreamlitのUploadedFileオブジェクトのリスト

    Returns:
        [{"maker": "CANON", "model": "EOS Kiss X9", "price_tax_in": 55000}, ...]
    """
    client = anthropic.Anthropic()

    content = []

    # 画像を全部まとめてClaudeに渡す
    for f in uploaded_files:
        image_bytes = f.read()
        encoded = encode_image(image_bytes)

        # 拡張子からメディアタイプを判定
        ext = Path(f.name).suffix.lower()
        media_type_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        media_type = media_type_map.get(ext, "image/jpeg")

        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": encoded,
            },
        })

    # テキスト指示
    content.append({
        "type": "text",
        "text": """これらはHard-Off（ハードオフ）の中古カメラの値札写真です。
各カメラの以下の情報を正確に読み取り、JSONのリスト形式のみで返答してください。
他の文章は不要です。JSONのみ返してください。

抽出する情報：
- maker: メーカー名（例: CANON, NIKON, SONY, OLYMPUS, PANASONIC, FUJIFILM, CASIO, PENTAX）
- model: 型番（例: EOS Kiss X9, COOLPIX P600, α NEX-3）
- price_tax_in: 税込価格（数字のみ、例: 16500）

出力形式：
[
  {"maker": "CANON", "model": "EOS Kiss X9", "price_tax_in": 55000},
  {"maker": "NIKON", "model": "D50", "price_tax_in": 9900}
]

注意点：
- 型番は正確に読み取ること（例: EOS Kiss Digital X, COOLPIX 3200 など）
- 価格は「税込」の金額を使う（赤字の大きな数字）
- 1枚の写真に複数台写っている場合は全台分を抽出する
- 読み取れない場合はそのアイテムをスキップする""",
    })

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2048,
        messages=[{"role": "user", "content": content}],
    )

    raw_text = response.content[0].text.strip()

    # JSONを抽出（```json ... ``` で囲まれている場合も対応）
    json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
    if not json_match:
        return []

    cameras = json.loads(json_match.group())
    return cameras
