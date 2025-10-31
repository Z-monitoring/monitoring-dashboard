# app.py
import io
import pandas as pd
import numpy as np
import altair as alt
import streamlit as st

st.set_page_config(page_title='監視エラー 可視化', layout='wide')
st.title('監視エラー可視化アプリ')

st.markdown("""
**機能**
1. Excel（Sheet1）を読み込み（アップロード or カレントの`監視エラー.xlsx`）
2. 全体／host別／connector別の件数を **日次・週次・月次** でグラフ表示
3. 直近期間と前期間の **増加率** を表示
""")

# --- Data loader ---
@st.cache_data
def load_data(file_bytes: bytes = None, fallback_path: str = '監視エラー.xlsx'):
    if file_bytes is not None:
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name='Sheet1', engine='openpyxl')
    else:
        # カレントにファイルがある場合の自動読み込み
        df = pd.read_excel(fallback_path, sheet_name='Sheet1', engine='openpyxl')

    # cleaning
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp']).copy()
    df['host'] = df['host'].astype(str).str.strip()
    df['url'] = df['url'].astype(str).str.strip()
    df['connector'] = df['connector'].astype(str).str.strip()

    # タイムゾーン（任意）：naiveならAsia/Tokyoとして扱う
    if df['timestamp'].dt.tz is None:
        df['timestamp'] = df['timestamp'].dt.tz_localize('Asia/Tokyo', ambiguous='NaT', nonexistent='shift_forward')
    return df

uploaded = st.file_uploader('Excelファイル（監視エラー.xlsx）を選択', type=['xlsx'])

try:
    df = load_data(uploaded.getvalue() if uploaded else None)
except Exception as e:
    st.error(f'読み込みエラー: {e}')
    st.stop()

# --- Sidebar controls ---
freq_label = st.sidebar.radio('集計粒度', ['日次','週次','月次'], index=0)
freq_map = {'日次': 'D', '週次': 'W-MON', '月次': 'M'}
freq = freq_map[freq_label]

dim_label = st.sidebar.radio('集計軸', ['全体','host','connector'], index=0)

# 期間フィルター
min_date = df['timestamp'].min().date()
max_date = df['timestamp'].max().date()
start, end = st.sidebar.date_input('期間', (min_date, max_date), min_value=min_date, max_value=max_date)
if isinstance(start, tuple) or isinstance(end, tuple):  # streamlitの仕様吸収
    start, end = start[0], end[0]
mask = (df['timestamp'].dt.date >= start) & (df['timestamp'].dt.date <= end)
df = df.loc[mask].copy()

# URLキーワード（任意）
kw = st.sidebar.text_input('URLキーワード（任意フィルター）')
if kw:
    df = df[df['url'].str.contains(kw, case=False, na=False)]

# --- Aggregation ---
if dim_label == '全体':
    grouped = df.groupby(pd.Grouper(key='timestamp', freq=freq)).size().rename('count').reset_index()
else:
    grouped = df.groupby([dim_label, pd.Grouper(key='timestamp', freq=freq)]).size().rename('count').reset_index()

# --- Chart ---
if dim_label == '全体':
    chart = alt.Chart(grouped).mark_line(point=True).encode(
        x=alt.X('timestamp:T', title=f'{freq_label}'),
        y=alt.Y('count:Q', title='件数'),
        tooltip=['timestamp:T','count:Q']
    )
else:
    # Top N選択
    topn = st.sidebar.slider('表示する上位グループ数', 3, 20, 10)
    latest_totals = grouped.groupby(dim_label)['count'].sum().sort_values(ascending=False).head(topn).index.tolist()
    grouped = grouped[grouped[dim_label].isin(latest_totals)]
    chart = alt.Chart(grouped).mark_line(point=True).encode(
        x=alt.X('timestamp:T', title=f'{freq_label}'),
        y=alt.Y('count:Q', title='件数'),
        color=alt.Color(f'{dim_label}:N', title=dim_label),
        tooltip=['timestamp:T', 'count:Q', alt.Tooltip(f'{dim_label}:N', title=dim_label)]
    )

st.altair_chart(chart.properties(width=1100, height=380), use_container_width=True)

# --- Growth (増加率) ---
st.subheader('増加率（当期 vs 前期）')

def show_metrics(g, label_name=None):
    g = g.sort_values('timestamp').copy()
    g['pct_change'] = g['count'].pct_change()
    if len(g) >= 2:
        last = g.iloc[-1]
        prev = g.iloc[-2]
        delta = (last['count'] - prev['count'])
        pct = g['pct_change'].iloc[-1]
        label = f"{prev['timestamp'].date()} → {last['timestamp'].date()}"
        if label_name:
            label = f"{label_name}｜{label}"
        st.metric(
            label=label,
            value=f"{int(last['count'])} 件",
            delta=f"{int(delta):+d} 件 / {pct*100:.1f} %" if pd.notna(pct) else "—"
        )
    else:
        st.info('増加率を計算するには2期間以上が必要です')

if dim_label == '全体':
    show_metrics(grouped)
else:
    cols = st.columns(4)
    # グループ毎にメトリクスを表示（最大12）
    by_groups = []
    for name, g in grouped.groupby(dim_label):
        g = g.sort_values('timestamp')
        if len(g) >= 2:
            last = g.iloc[-1]['count']
            prev = g.iloc[-2]['count']
            pct = (last - prev) / prev if prev != 0 else np.nan
            by_groups.append((name, g, pct))
    by_groups = sorted(by_groups, key=lambda x: (x[2] if pd.notna(x[2]) else -np.inf), reverse=True)[:12]
    for i, (name, g, _) in enumerate(by_groups):
        with cols[i % len(cols)]:
            show_metrics(g, label_name=str(name))

# --- Data preview & export ---
with st.expander('データ（先頭）を確認'):
    st.dataframe(df.head(20))

if st.button('集計データをCSVでダウンロード'):
    if dim_label == '全体':
        out = grouped.copy()
    else:
        out = grouped.copy().sort_values([dim_label, 'timestamp'])
    st.download_button('CSVを保存', out.to_csv(index=False).encode('utf-8'), file_name='aggregated.csv', mime='text/csv')

st.caption('定義: 増加率 = (当期件数 - 前期件数) / 前期件数。前期が0件のときは表示不可。')
