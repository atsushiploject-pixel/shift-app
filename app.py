import pandas as pd
import streamlit as st
from google.cloud import firestore
import datetime
import calendar

# --- 1. 認証とデータベース接続 ---
# 【重要】""の中を、あなたがアップロードしたJSONファイルの名前に書き換えてください！
key_file_path = "shift-ap-65c191bee146.json" # ← ここのファイル名を必ず書き換えてください

try:
    db = firestore.Client.from_service_account_json(key_file_path)
except Exception as e:
    st.error("データベースへの接続に失敗しました。JSONキーファイルの名前が正しいか確認してください。")
    st.stop()

# --- 2. 各画面の機能を関数として定義 ---

def main_menu():
    """メインメニュー画面"""
    st.title('シフト管理アプリ')
    st.write('左のメニューから、実行したい作業を選んでください。')
    # ここに、将来的にお知らせなどを表示できる

def master_management():
    """マスタ管理画面"""
    st.title('マスタ情報管理')
    st.write('利用者やスタッフの基本情報を登録・編集します。')

    # --- サブメニュー ---
    master_menu = st.selectbox('どちらの情報を管理しますか？', ['利用者マスタ', 'スタッフマスタ'])

    if master_menu == 'スタッフマスタ':
        # (この部分は変更ありません)
        st.subheader('スタッフ一覧')
        try:
            staff_ref = db.collection('staff')
            all_staff = [doc.to_dict() for doc in staff_ref.stream()]
            if all_staff:
                st.dataframe(all_staff)
            else:
                st.info('まだスタッフが登録されていません。')
        except Exception as e:
            st.error(f"スタッフ情報の読み込み中にエラーが発生しました: {e}")

        st.subheader('新しいスタッフを登録')
        with st.form("new_staff_form", clear_on_submit=True):
            staff_name = st.text_input('スタッフ名')
            staff_type = st.selectbox('雇用形態', ['常勤', 'パート'])
            weekdays = ["月", "火", "水", "木", "金", "土"] #日曜は定休
            default_work_days = st.multiselect('基本出勤曜日を選択', weekdays)
            submitted = st.form_submit_button("この内容で登録する")
            if submitted:
                if staff_name:
                    try:
                        new_staff_data = {'name': staff_name, 'type': staff_type, 'defaultWorkDays': default_work_days}
                        db.collection('staff').add(new_staff_data)
                        st.success(f"スタッフ「{staff_name}」さんを登録しました。")
                    except Exception as e:
                        st.error(f"登録中にエラーが発生しました: {e}")
                else:
                    st.warning('スタッフ名を入力してください。')

    elif master_menu == '利用者マスタ':
        # --- ここからが新しく追加・変更された部分です ---
        st.subheader('利用者一覧')
        try:
            users_ref = db.collection('users')
            all_users = [doc.to_dict() for doc in users_ref.stream()]
            if all_users:
                st.dataframe(all_users)
            else:
                st.info('まだ利用者が登録されていません。')
        except Exception as e:
            st.error(f"利用者情報の読み込み中にエラーが発生しました: {e}")
        
        st.subheader('新しい利用者を登録')
        with st.form("new_user_form", clear_on_submit=True):
            user_name = st.text_input('利用者名')
            care_level = st.selectbox('介護度', ['要介護1', '要介護2', '要介護3', '要介護4', '要介護5'])
            
            # 食事形態もFirestoreから読み込んで選択肢にするのが理想ですが、まずは固定で実装
            meal_type = st.selectbox('食事形態', ['常食', 'やわらか食', 'さばなし', '肉無し', '軟飯', 'おかゆ', '揚げ物無し'])
            
            weekdays = ["月", "火", "水", "木", "金", "土"] #日曜は定休
            default_use_days = st.multiselect('基本利用曜日を選択', weekdays)
            
            submitted = st.form_submit_button("この内容で登録する")
            if submitted:
                if user_name:
                    try:
                        new_user_data = {
                            'name': user_name,
                            'careLevel': care_level,
                            'mealType': meal_type,
                            'defaultUseDays': default_use_days
                        }
                        db.collection('users').add(new_user_data)
                        st.success(f"利用者「{user_name}」さんを登録しました。")
                    except Exception as e:
                        st.error(f"登録中にエラーが発生しました: {e}")
                else:
                    st.warning('利用者名を入力してください。')

def create_shift():
    """あらたにシフトつくる画面"""
    st.title('📅 あらたにシフトつくる')

    # --- session_stateの初期化 ---
    # 'generated_shift'という記憶領域がなければ、Noneで初期化
    if 'generated_shift' not in st.session_state:
        st.session_state.generated_shift = None

    # --- Step 1: 希望休の入力フォーム ---
    with st.form("holiday_request_form"):
        st.header('Step 1: 対象年月と希望休を入力')
        col1, col2 = st.columns(2)
        with col1:
            target_year = st.number_input('年', min_value=2024, max_value=2030, value=datetime.date.today().year)
        with col2:
            target_month = st.number_input('月', min_value=1, max_value=12, value=datetime.date.today().month)
        
        try:
            staff_ref = db.collection('staff')
            all_staff = [doc.to_dict() for doc in staff_ref.stream()]
            staff_names = [staff['name'] for staff in all_staff if 'name' in staff]
        except Exception as e:
            st.error(f"スタッフ情報の読み込みエラー: {e}")
            st.stop()

        st.subheader('スタッフの希望休')
        holiday_requests = {}
        for staff_name in staff_names:
            holiday_requests[staff_name] = st.multiselect(
                f'{staff_name}さんの希望休', options=list(range(1, calendar.monthrange(target_year, target_month)[1] + 1))
            )
        
        submitted = st.form_submit_button("Step 2へ進む → シフトを自動生成＆分析")

        if submitted:
            # --- ボタンが押されたら、シフトを生成して「記憶」させる ---
            with st.spinner('シフトを生成しています...'):
                # (ここから下のロジックは前回とほぼ同じ)
                users_ref = db.collection('users')
                user_list = [doc.to_dict() for doc in users_ref.stream()]
                num_days = calendar.monthrange(target_year, target_month)[1]
                weekdays = ["月", "火", "水", "木", "金", "土", "日"]
                calendar_info = [{'date': d, 'weekday': weekdays[calendar.weekday(target_year, target_month, d)]} for d in range(1, num_days + 1)]
                shift_schedule = {}
                for day_info in calendar_info:
                    day, weekday = day_info['date'], day_info['weekday']
                    attending_staff = [s['name'] for s in all_staff if weekday in s.get('defaultWorkDays', []) and day not in holiday_requests.get(s.get('name'), [])]
                    attending_users = [u['name'] for u in user_list if weekday in u.get('defaultUseDays', [])]
                    date_key = f"{target_year}-{str(target_month).zfill(2)}-{str(day).zfill(2)}"
                    shift_schedule[date_key] = {'staff': attending_staff, 'users': attending_users}
                
                # ★★★ 生成した結果を、ただの変数ではなく「記憶領域」に保存 ★★★
                st.session_state.generated_shift = {
                    "year": target_year,
                    "month": target_month,
                    "schedule": shift_schedule,
                    "all_staff": all_staff,
                    "user_list": user_list
                }
                st.success("シフトのたたき台生成が完了しました。Step3で内容を確認し、保存してください。")

    # --- Step 2: シフトが「記憶」されていれば、分析結果と保存ボタンを表示 ---
    if st.session_state.generated_shift:
        
        # 記憶したデータを取り出す
        year = st.session_state.generated_shift['year']
        month = st.session_state.generated_shift['month']
        schedule = st.session_state.generated_shift['schedule']
        all_staff_data = st.session_state.generated_shift['all_staff']
        user_list_data = st.session_state.generated_shift['user_list']

        st.header('Step 3: 分析結果の確認と保存')
        # (分析ロジックは省略)
        # ...

        with st.expander("生成されたシフトの全体像（生データ）を確認する"):
            st.json(schedule)

        if st.button('このシフトのたたき台をデータベースに保存する'):
            with st.spinner('データベースに保存しています...'):
                num_days = calendar.monthrange(year, month)[1]
                staff_schedule_to_save = {s['name']: {str(d): ('出' if s['name'] in schedule.get(f"{year}-{str(month).zfill(2)}-{str(d).zfill(2)}", {}).get('staff', []) else '') for d in range(1, num_days+1)} for s in all_staff_data}
                user_schedule_to_save = {u['name']: {str(d): ('○' if u['name'] in schedule.get(f"{year}-{str(month).zfill(2)}-{str(d).zfill(2)}", {}).get('users', []) else '') for d in range(1, num_days+1)} for u in user_list_data}
                
                month_doc_id = f"{year}-{str(month).zfill(2)}"
                db.collection('shifts').document(month_doc_id).set({
                    'staff_schedule': staff_schedule_to_save,
                    'user_schedule': user_schedule_to_save,
                    'last_updated': firestore.SERVER_TIMESTAMP
                })
                st.success(f"{month_doc_id}のシフトを保存しました！")
                
                # 保存が完了したら、記憶をクリアして初期状態に戻る
                st.session_state.generated_shift = None
                st.balloons()

def view_shift():
    """シフトを見る画面"""
    st.title('📄 シフトを見る・修正する')
    st.write('指定した月のシフトの状況を、表形式で確認・修正できます。')

    col1, col2 = st.columns(2)
    with col1:
        target_year = st.number_input('年', min_value=2024, max_value=2030, value=datetime.date.today().year, key='view_year')
    with col2:
        target_month = st.number_input('月', min_value=1, max_value=12, value=datetime.date.today().month, key='view_month')

    month_doc_id = f"{target_year}-{str(target_month).zfill(2)}"
    shift_doc_ref = db.collection('shifts').document(month_doc_id)
    shift_doc = shift_doc_ref.get()

    if not shift_doc.exists:
        st.warning(f"保存済みのシフトがありません。「あらたにシフトつくる」画面で先に生成・保存してください。")
        st.stop()
    
    shift_data = shift_doc.to_dict()
    
    # --- スケジュール修正機能 ---
    st.header('クイック修正')
    user_names = list(shift_data.get('user_schedule', {}).keys())
    if user_names:
        c1, c2, c3 = st.columns(3)
        with c1:
            selected_user = st.selectbox('① 利用者を選択', user_names, key='qs_user')
        with c2:
            num_days = calendar.monthrange(target_year, target_month)[1]
            selected_day = st.selectbox('② 日付を選択', list(range(1, num_days + 1)), key='qs_day')
        with c3:
            st.write("③ 実行する操作")
            if st.button('利用を「お休み」に変更'):
                try:
                    shift_doc_ref.update({f'user_schedule.{selected_user}.{str(selected_day)}': '休'})
                    st.success(f'更新しました！')
                    st.rerun() # 画面を自動でリフレッシュ
                except Exception as e: 
                    st.error(f"更新エラー: {e}")

    # --- シフト表の表示 ---
    st.header('現在のシフト状況')

    st.subheader('スタッフ シフト表')
    staff_schedule = shift_data.get('staff_schedule', {})
    if staff_schedule:
        staff_df = pd.DataFrame.from_dict(staff_schedule, orient='index')
        # 日付順に列を並び替え
        sorted_columns = sorted(staff_df.columns, key=int)
        st.dataframe(staff_df[sorted_columns])
    
    st.subheader('利用者 スケジュール表')
    user_schedule = shift_data.get('user_schedule', {})
    if user_schedule:
        user_df = pd.DataFrame.from_dict(user_schedule, orient='index')
        # 日付順に列を並び替え
        sorted_columns = sorted(user_df.columns, key=int)
        st.dataframe(user_df[sorted_columns])

def edit_shift():
    """修正する画面"""
    st.title('修正する')
    # TODO: ここに、会話形式の修正フローを実装

# --- 3. サイドバーを使った画面遷移 ---
st.sidebar.title('メインメニュー')
page_options = {
    'メインメニュー': main_menu,
    'シフトを見る': view_shift,
    '修正する': edit_shift,
    'あらたにシフトつくる': create_shift,
    '登録情報の変更': master_management,
}

selected_page = st.sidebar.radio('操作を選択してください', list(page_options.keys()))

# 選択されたページに応じて、対応する関数を実行
page_options[selected_page]()