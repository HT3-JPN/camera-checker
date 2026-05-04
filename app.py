"""
app.py
中古カメラ メルカリ相場チェッカー
Streamlit Webアプリ メインファイル

使い方:
    streamlit run app.py
"""

import io
import os
import sys
import subprocess
import streamlit as st
import pandas as pd
from camera_ocr import extract_cameras_from_images
from aucfan_scraper import batch_search

# ─────────────────────────────────────────
# Playwright ブラウザのインストール（Streamlit Cloud用）
# ─────────────────────────────────────────
@st.cache_resource
def setup_playwright():
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True, capture_output=True
        )
    except Exception:
        pass

setup_playwright()

# ─────────────────────────────────────────
# ページ設定
# ─────────────────────────────────────────
st.set_page_config(
    page_title="中古カメラ 相場チェッカー",
    page_icon="📷",
    layout="wide",
)

# ─────────────────────────────────────────
# パスワード認証
# ─────────────────────────────────────────
def check_password():
    correct_password = st.secrets.get("APP_PASSWORD", "")

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("📷 中古カメラ 相場チェッカー")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("🔒 ログイン")
        password = st.text_input("パスワードを入力してください", type="password")
        if st.button("ログイン", use_container_width=True):
            if password == correct_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("パスワードが違います")
    return False

if not check_password():
    st.stop()

# ─────────────────────────────────────────
# サイドバー：設定
# ─────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 設定")

    api_key = st.text_input(
        "Claude API Key",
        type="password",
        help="Anthropic の API キーを入力してください",
        placeholder="sk-ant-...",
    )

    st.markdown("---")
    st.markdown("#### 使い方")
    st.markdown("""
1. 🔑 API Keyをサイドバーに入力
2. 📷 Hard-Offの値札写真をアップロード
3. 🔍「写真からカメラ情報を読み取る」をクリック
4. 🚀「相場を調べる」をクリック
5. 📥 結果をExcelでダウンロード
""")
    st.markdown("---")
    st.markdown("**対応形式:** JPG / PNG / WEBP")
    st.markdown("**1回最大:** 10枚まで")


# ─────────────────────────────────────────
# タイトル
# ─────────────────────────────────────────
st.title("📷 中古カメラ 相場チェッカー")
st.caption("Hard-Offの値札写真をアップロードするだけで、メルカリ90日間相場を自動調査します")


# ─────────────────────────────────────────
# 検索実行・結果表示（共通関数）
# ─────────────────────────────────────────
def run_search(df: pd.DataFrame):
    """相場検索を実行して結果を表示"""

    if df.empty:
        st.warning("カメラが1台も入力されていません")
        return

    cameras = []
    for _, row in df.iterrows():
        maker = str(row.get("メーカー", "")).strip()
        model = str(row.get("型番", "")).strip()
        price = row.get("税込仕入価格", 0)
        if maker and model:
            cameras.append({"maker": maker, "model": model, "price_tax_in": int(price or 0)})

    if not cameras:
        st.warning("有効なカメラデータがありません")
        return

    # プログレスバー
    progress_bar = st.progress(0)
    status_text = st.empty()

    def update_progress(current, total, name):
        if total > 0:
            progress_bar.progress(current / total)
        status_text.text(f"🔍 調査中 ({current}/{total}): {name}")

    # 検索実行
    results = batch_search(cameras, progress_callback=update_progress)

    progress_bar.progress(1.0)
    status_text.text("✅ 完了！")

    # ─────────────────────────────
    # 結果表示
    # ─────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 調査結果")

    results_df = pd.DataFrame(results)

    # 仕入比較列を追加
    def judge(row):
        median = row.get("中央値")
        cost   = row.get("仕入価格(税込)", 0)
        if median is None or pd.isna(median):
            return "データなし"
        diff = int(median) - int(cost)
        if diff >= 3000:
            return f"✅ +¥{diff:,}"
        elif diff >= 0:
            return f"🔶 +¥{diff:,}"
        else:
            return f"❌ ¥{diff:,}"

    results_df["仕入比較"] = results_df.apply(judge, axis=1)

    display_cols = ["メーカー", "型番", "仕入価格(税込)", "件数", "中央値", "最高値", "最低値", "仕入比較"]

    st.dataframe(
        results_df[display_cols],
        use_container_width=True,
        column_config={
            "仕入価格(税込)": st.column_config.NumberColumn(format="¥%d"),
            "中央値":         st.column_config.NumberColumn(format="¥%d"),
            "最高値":         st.column_config.NumberColumn(format="¥%d"),
            "最低値":         st.column_config.NumberColumn(format="¥%d"),
        },
        hide_index=True,
    )

    # サマリー
    valid = results_df[results_df["中央値"].notna()]
    if not valid.empty:
        col1, col2, col3 = st.columns(3)
        profitable = valid[valid["中央値"] >= valid["仕入価格(税込)"]]
        col1.metric("調査台数", f"{len(results_df)}台")
        col2.metric("利益見込みあり", f"{len(profitable)}台")
        avg_margin = int((valid["中央値"] - valid["仕入価格(税込)"]).mean())
        col3.metric("平均差額（中央値-仕入）", f"¥{avg_margin:,}")

    # ダウンロード
    st.markdown("#### 📥 ダウンロード")
    col_dl1, col_dl2 = st.columns(2)

    with col_dl1:
        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
            results_df[display_cols].to_excel(writer, index=False, sheet_name="相場調査")
            ws = writer.sheets["相場調査"]
            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                ws.column_dimensions[col[0].column_letter].width = max_len + 4
        st.download_button(
            "📊 Excelダウンロード (.xlsx)",
            data=excel_buf.getvalue(),
            file_name="camera_mercari_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with col_dl2:
        csv_data = results_df[display_cols].to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "📄 CSVダウンロード (.csv)",
            data=csv_data.encode("utf-8-sig"),
            file_name="camera_mercari_report.csv",
            mime="text/csv",
        )

    # aucfan リンク集
    with st.expander("🔗 aucfan 検索URLリスト（確認用）"):
        for _, row in results_df.iterrows():
            st.markdown(f"- **{row['メーカー']} {row['型番']}**: [aucfanで確認]({row['aucfan URL']})")


# ─────────────────────────────────────────
# メインコンテンツ（タブ）
# ─────────────────────────────────────────
tab1, tab2 = st.tabs(["📷 写真から自動読み取り", "⌨️ 手動でリスト入力"])


# ════════════════════════════════════════
# タブ1：写真アップロード
# ════════════════════════════════════════
with tab1:
    uploaded_files = st.file_uploader(
        "Hard-Offの値札写真をここにドロップ（または選択）",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        help="1枚に複数台写っていても全台自動抽出します",
    )

    if uploaded_files:
        st.caption(f"{len(uploaded_files)}枚アップロード済み")
        cols = st.columns(min(len(uploaded_files), 5))
        for i, f in enumerate(uploaded_files[:5]):
            with cols[i]:
                st.image(f, use_column_width=True, caption=f.name)

        # STEP1: 写真読み取り
        if st.button("📖 写真からカメラ情報を読み取る", type="secondary"):
            if not api_key:
                st.error("⚠️ サイドバーにClaude API Keyを入力してください")
            else:
                os.environ["ANTHROPIC_API_KEY"] = api_key
                with st.spinner("📖 写真を読み取り中（Claude AIが解析しています）..."):
                    try:
                        for f in uploaded_files:
                            f.seek(0)
                        cameras = extract_cameras_from_images(uploaded_files)
                        st.session_state["cameras_photo"] = cameras
                        st.success(f"✅ {len(cameras)}台のカメラを検出しました")
                    except Exception as e:
                        st.error(f"❌ 読み取りエラー: {e}")

    # STEP2: 読み取り結果を編集 → 検索
    if st.session_state.get("cameras_photo"):
        st.markdown("#### 読み取り結果（修正可能）")
        df_photo = pd.DataFrame(st.session_state["cameras_photo"])
        df_photo.columns = ["メーカー", "型番", "税込仕入価格"]

        edited_df = st.data_editor(
            df_photo,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "税込仕入価格": st.column_config.NumberColumn(format="¥%d"),
            },
            key="editor_photo",
        )

        if st.button("🚀 相場を調べる", type="primary", key="search_photo"):
            if not api_key:
                st.error("⚠️ サイドバーにClaude API Keyを入力してください")
            else:
                os.environ["ANTHROPIC_API_KEY"] = api_key
                run_search(edited_df)


# ════════════════════════════════════════
# タブ2：手動入力
# ════════════════════════════════════════
with tab2:
    st.caption("カメラ情報を直接入力して調査できます。写真不要です。")

    sample = pd.DataFrame([
        {"メーカー": "CANON",     "型番": "EOS Kiss Digital X", "税込仕入価格": 11000},
        {"メーカー": "NIKON",     "型番": "COOLPIX P600",       "税込仕入価格": 16500},
        {"メーカー": "SONY",      "型番": "NEX-3",              "税込仕入価格": 16500},
        {"メーカー": "PANASONIC", "型番": "DMC-FX30",           "税込仕入価格": 6600},
    ])

    manual_df = st.data_editor(
        sample,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "税込仕入価格": st.column_config.NumberColumn(format="¥%d"),
        },
        key="editor_manual",
    )

    if st.button("🚀 相場を調べる", type="primary", key="search_manual"):
        if not api_key:
            st.error("⚠️ サイドバーにClaude API Keyを入力してください")
        else:
            os.environ["ANTHROPIC_API_KEY"] = api_key
            run_search(manual_df)


# ─────────────────────────────────────────
# フッター
# ─────────────────────────────────────────
st.markdown("---")
st.caption("データソース: aucfan.com（メルカリ 直近90日）| 価格は参考値です。実際の取引価格は変動します。")
