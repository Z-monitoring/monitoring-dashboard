import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
from pathlib import Path
 
# ページ設定
st.set_page_config(page_title="エラー可視化ダッシュボード", page_icon=":bar_chart:")
 
# データ保存用CSVファイルとバックアップフォルダ
DATA_FILE = "error_data.csv"
BACKUP_FOLDER = Path("backups")
BACKUP_FOLDER.mkdir(exist_ok=True)
 
# CSVファイルが存在すれば読み込み、なければ空のデータフレームを作成
if os.path.exists(DATA_FILE):
    df = pd.read_csv(DATA_FILE, parse_dates=["timestamp"])
else:
    df = pd.DataFrame(columns=["timestamp", "error_destination", "connector_server", "connection_type"])
 
# 入力フォーム
with st.form("error_input_form"):
    st.subheader("エラー情報の入力")
    input_date = st.date_input("日付", value=datetime.today())
    error_destination = st.selectbox("エラーの宛先", ["ServerA", "ServerB", "ServerC"])
    connector_server = st.selectbox("コネクタサーバ", ["Connector1", "Connector2", "Connector3"])
    connection_type = st.selectbox("接続方式", ["有線", "無線"])
    submitted = st.form_submit_button("追加")
 
# 入力があればCSVに追記し、バックアップも保存
if submitted:
    new_entry = pd.DataFrame([{
        "timestamp": pd.to_datetime(input_date),
        "error_destination": error_destination,
        "connector_server": connector_server,
        "connection_type": connection_type
    }])
    df = pd.concat([df, new_entry], ignore_index=True)
    df.to_csv(DATA_FILE, index=False)
 
    # バックアップファイル名にタイムスタンプを付けて保存
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_FOLDER / f"error_data_backup_{timestamp_str}.csv"
    df.to_csv(backup_file, index=False)
 
    st.success("エラー情報を追加し、バックアップを保存しました")
 
# データが存在する場合のみ可視化
if not df.empty:
    # 時系列列の追加（フォーマット調整）
    df["date"] = df["timestamp"].dt.strftime("%Y/%m/%d")
    df["month"] = df["timestamp"].dt.strftime("%Y/%m")
    df["year"] = df["timestamp"].dt.year
 
    # サイドバーでフィルターと削除機能
    st.sidebar.header("フィルター")
    selected_destination = st.sidebar.multiselect("エラーの宛先", df["error_destination"].unique(), default=df["error_destination"].unique())
    selected_connector = st.sidebar.multiselect("コネクタサーバ", df["connector_server"].unique(), default=df["connector_server"].unique())
    selected_connection = st.sidebar.multiselect("接続方式", df["connection_type"].unique(), default=df["connection_type"].unique())
 
    # 削除機能
    st.sidebar.header("入力データの削除")
    if st.sidebar.button("最新の入力を削除"):
        df = df.iloc[:-1]
        df.to_csv(DATA_FILE, index=False)
        st.sidebar.success("最新の入力を削除しました")
 
    filtered_df = df[
        df["error_destination"].isin(selected_destination) &
        df["connector_server"].isin(selected_connector) &
        df["connection_type"].isin(selected_connection)
    ]
 
    # タブで表示切り替え
    tab1, tab2, tab3, tab4 = st.tabs(["全体", "宛先別", "コネクタサーバ別", "接続方式別"])
 
    def plot_error_counts(group_df, group_col, title_prefix):
        if group_df.empty:
            st.warning(f"{title_prefix} に該当するデータがありません。")
            return
 
        if group_col:
            daily = group_df.groupby([group_col, "date"]).size().reset_index(name="count")
            if not daily.empty:
                fig_daily = px.bar(daily, x="date", y="count", color=group_col, title=f"{title_prefix} - 日次")
                st.plotly_chart(fig_daily)
 
            monthly = group_df.groupby([group_col, "month"]).size().reset_index(name="count")
            if not monthly.empty:
                fig_monthly = px.bar(monthly, x="month", y="count", color=group_col, title=f"{title_prefix} - 月次")
                st.plotly_chart(fig_monthly)
 
            yearly = group_df.groupby([group_col, "year"]).size().reset_index(name="count")
            if not yearly.empty:
                fig_yearly = px.bar(yearly, x="year", y="count", color=group_col, title=f"{title_prefix} - 年次")
                st.plotly_chart(fig_yearly)
        else:
            daily = group_df.groupby("date").size().reset_index(name="count")
            if not daily.empty:
                fig_daily = px.bar(daily, x="date", y="count", title=f"{title_prefix} - 日次")
                st.plotly_chart(fig_daily)
 
            monthly = group_df.groupby("month").size().reset_index(name="count")
            if not monthly.empty:
                fig_monthly = px.bar(monthly, x="month", y="count", title=f"{title_prefix} - 月次")
                st.plotly_chart(fig_monthly)
 
            yearly = group_df.groupby("year").size().reset_index(name="count")
            if not yearly.empty:
                fig_yearly = px.bar(yearly, x="year", y="count", title=f"{title_prefix} - 年次")
                st.plotly_chart(fig_yearly)
 
    with tab1:
        plot_error_counts(filtered_df, group_col=None, title_prefix="全体")
 
    with tab2:
        plot_error_counts(filtered_df, group_col="error_destination", title_prefix="宛先別")
 
    with tab3:
        plot_error_counts(filtered_df, group_col="connector_server", title_prefix="コネクタサーバ別")
 
    with tab4:
        plot_error_counts(filtered_df, group_col="connection_type", title_prefix="接続方式別")
