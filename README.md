# 📷 中古カメラ 相場チェッカー

Hard-Off の値札写真をアップロードするだけで、aucfan からメルカリの90日間相場を自動取得するWebアプリです。

## セットアップ（PC でローカル実行）

```bash
# 1. リポジトリに移動
cd camera-checker

# 2. 必要パッケージをインストール
pip install -r requirements.txt

# 3. Playwright のブラウザをインストール
playwright install chromium

# 4. アプリを起動
streamlit run app.py
```

ブラウザが自動で開き、`http://localhost:8501` でアプリが使えます。

## Streamlit Cloud へのデプロイ（iPhone から使えるようにする）

1. このフォルダを GitHub リポジトリとして公開（Private でOK）
2. [Streamlit Cloud](https://streamlit.io/cloud) にアクセス
3. 「New app」→ GitHubリポジトリを選択 → `app.py` を指定
4. 「Advanced settings」→ Secrets に以下を追加：
   ```
   ANTHROPIC_API_KEY = "sk-ant-あなたのキー"
   ```
5. 「Deploy」ボタンをクリック

デプロイ後、発行された URL を iPhone の Safari で開くだけで使えます！

## ファイル構成

```
camera-checker/
├── app.py              # メインアプリ
├── camera_ocr.py       # Claude API で写真→カメラ情報を抽出
├── aucfan_scraper.py   # aucfan から価格データを取得
├── requirements.txt    # Python パッケージ
├── packages.txt        # Streamlit Cloud 用システムパッケージ
└── .streamlit/
    └── secrets.toml    # API Key（GitHub にアップしない）
```

## 使い方

1. サイドバーに Claude API Key を入力
2. 「📷 写真から自動読み取り」タブで写真をアップロード
3. 「写真からカメラ情報を読み取る」をクリック
4. 読み取り結果を確認・修正
5. 「相場を調べる」をクリック
6. 結果テーブルを確認 → Excel でダウンロード
