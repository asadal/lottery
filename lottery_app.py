import streamlit as st
import pandas as pd
import io
import re
import time
import string

def sanitize_filename(filename):
    """
    파일명에서 사용할 수 없는 문자를 제거하거나 대체합니다.
    한글을 포함한 모든 유니코드 문자를 허용하되, Windows와 Unix 시스템에서 금지된 문자는 대체합니다.
    """
    # Windows에서 금지된 문자: < > : " / \ | ? *
    # Unix에서는 /와 NUL 문자만 금지
    forbidden_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(forbidden_chars, '_', filename)
    sanitized = sanitized.strip()  # 앞뒤 공백 제거
    if not sanitized:
        sanitized = "당첨자_목록"  # 기본 파일명 설정
    return sanitized

def load_excel(file):
    try:
        df = pd.read_excel(file)
        return df
    except Exception as e:
        st.error(f"엑셀 파일을 읽는 중 오류가 발생했습니다: {e}")
        return None

def load_csv(file):
    try:
        df = pd.read_csv(file)
        return df
    except Exception as e:
        st.error(f"CSV 파일을 읽는 중 오류가 발생했습니다: {e}")
        return None

def load_google_sheet(url):
    """
    구글 시트 URL을 CSV 내보내기 URL로 변환하여 데이터를 로드합니다.
    """
    try:
        # URL에서 파일 ID와 gid 추출
        match = re.match(r'https://docs.google.com/spreadsheets/d/([a-zA-Z0-9-_]+).*gid=([0-9]+)', url)
        if not match:
            st.error("구글 시트 URL 형식이 올바르지 않습니다.")
            return None, None
        file_id, gid = match.groups()
        csv_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv&gid={gid}"
        df = pd.read_csv(csv_url)
        return df, f"GoogleSheet_{file_id}"
    except Exception as e:
        st.error(f"구글 시트를 로드하는 중 오류가 발생했습니다: {e}")
        return None, None

def initialize_session_state():
    if 'data' not in st.session_state:
        st.session_state.data = None
    if 'original_filename' not in st.session_state:
        st.session_state.original_filename = ""
    if 'winners' not in st.session_state:
        st.session_state.winners = pd.DataFrame()
    if 'previous_winners' not in st.session_state:
        st.session_state.previous_winners = pd.DataFrame()
    if 'current_round' not in st.session_state:
        st.session_state.current_round = 1

def reset_session_state():
    st.session_state.data = None
    st.session_state.original_filename = ""
    st.session_state.winners = pd.DataFrame()
    st.session_state.previous_winners = pd.DataFrame()
    st.session_state.current_round = 1
    st.rerun()

def main():
    # 페이지 설정: 타이틀, 레이아웃, 파비콘 설정
    st.set_page_config(
        page_title="랜덤 당첨자 추첨기",
        page_icon="🎉",  # 또는 파비콘 이미지 파일 경로 (예: "favicon.ico")
        layout="centered"
    )

    st.title("랜덤 당첨자 추첨기")
    
    # 대표 이미지 추가 (로컬 이미지 파일 또는 URL 사용 가능)
    # 로컬 이미지 파일을 사용할 경우, 이미지 파일을 프로젝트 폴더에 저장하고 파일명을 지정하세요.
    # 예: st.image("banner.png", use_column_width=True)
    # 온라인 이미지를 사용할 경우, 이미지 URL을 사용하세요.
    st.image("https://cdn-icons-png.flaticon.com/512/6662/6662916.png", width=80)
    
    st.write("""
        엑셀/CSV 파일을 업로드하거나 공개된 구글 시트 URL을 넣어주세요. 참가자 목록을 불러오고, 지정한 수만큼 랜덤으로 당첨자를 추첨해줍니다.
    """)
    initialize_session_state()

    # '초기화' 버튼 추가
    if st.button("Reload ⟳"):
        reset_session_state()

    # 데이터 소스 선택
    option = st.radio("데이터 소스 선택", ("엑셀/CSV 파일 업로드", "구글 시트 URL 입력"))

    if option == "엑셀/CSV 파일 업로드":
        uploaded_file = st.file_uploader("엑셀 파일(.xlsx) 또는 CSV 파일(.csv)을 업로드하세요", type=["xlsx", "csv"])
        if uploaded_file is not None:
            st.session_state.original_filename = uploaded_file.name
            if uploaded_file.name.endswith('.xlsx'):
                st.session_state.data = load_excel(uploaded_file)
            else:
                st.session_state.data = load_csv(uploaded_file)
    else:
        google_sheet_url = st.text_input("구글 시트 URL을 입력하세요")
        if google_sheet_url:
            data, original_filename = load_google_sheet(google_sheet_url)
            if data is not None:
                st.session_state.data = data
                st.session_state.original_filename = original_filename + ".csv"  # 기본 확장자 설정

    # 'previous_winners' 초기화 (data가 로드된 후에 설정)
    if st.session_state.data is not None and st.session_state.previous_winners.empty:
        st.session_state.previous_winners = pd.DataFrame(columns=['Draw Name'] + list(st.session_state.data.columns))

    if st.session_state.data is not None:
        st.success("데이터가 성공적으로 로드됐습니다!")
        st.dataframe(st.session_state.data.head())  # 데이터의 처음 몇 행 표시

        # 당첨자 수 입력
        total_entries = len(st.session_state.data)
        winner_num = st.number_input("당첨자 수를 입력하세요", min_value=1, max_value=total_entries, value=1, step=1)

        # '기존 당첨자 제외' 옵션 추가 (조건부 표시)
        exclude_previous = None  # 초기화
        if not st.session_state.previous_winners.empty:
            exclude_previous = st.checkbox("기존 당첨자 제외")

        # 추첨명 입력
        draw_name = st.text_input("추첨명을 입력하세요", value=f"추첨 {st.session_state.current_round}")

        # '기존 당첨자 보기' 버튼 추가 (조건부 표시)
        if not st.session_state.previous_winners.empty:
            if st.button("기존 당첨자 보기"):
                st.header("추첨별 당첨자 목록")
                draw_names = st.session_state.previous_winners['Draw Name'].unique()
                for draw in sorted(draw_names):
                    st.subheader(f"{draw}")
                    round_winners = st.session_state.previous_winners[st.session_state.previous_winners['Draw Name'] == draw].drop(columns=['Draw Name'])
                    st.dataframe(round_winners)
                    
                    # 다운로드 버튼 추가 (고유한 key 부여)
                    # Excel 다운로드 버튼
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        round_winners.to_excel(writer, index=False)
                    excel_buffer.seek(0)
                    sanitized_draw_name = sanitize_filename(draw)
                    download_filename_excel = f"{sanitized_draw_name}.xlsx"
                    st.download_button(
                        label=f"'{draw}' 당첨자 다운로드 (Excel)",
                        data=excel_buffer,
                        file_name=download_filename_excel,
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        key=f"download_{sanitized_draw_name}_excel"
                    )
                    
                    # CSV 다운로드 버튼
                    csv_data = round_winners.to_csv(index=False).encode('utf-8')
                    download_filename_csv = f"{sanitized_draw_name}.csv"
                    st.download_button(
                        label=f"'{draw}' 당첨자 다운로드 (CSV)",
                        data=csv_data,
                        file_name=download_filename_csv,
                        mime='text/csv',
                        key=f"download_{sanitized_draw_name}_csv"
                    )

        # 애니메이션을 위한 플레이스홀더 생성
        animation_placeholder = st.empty()

        if st.button("추첨하기"):
            # 추첨명 유효성 검사
            if not draw_name.strip():
                st.error("추첨명을 입력해주세요.")
            else:
                # 데이터에서 기존 당첨자를 제외
                if exclude_previous and not st.session_state.previous_winners.empty:
                    remaining_data = st.session_state.data[~st.session_state.data.apply(tuple,1).isin(
                        st.session_state.previous_winners.drop(columns=['Draw Name']).apply(tuple,1)
                    )]
                    remaining_entries = len(remaining_data)
                    if remaining_entries < winner_num:
                        st.error(f"기존 당첨자를 제외한 참가자 수가 당첨자 수({winner_num})보다 적습니다.")
                    else:
                        # 애니메이션 효과: 빠르게 랜덤 당첨자 목록을 변경하며 "롤링"하는 효과
                        animation_steps = 20  # 애니메이션 단계 수
                        for i in range(animation_steps):
                            temp_winners = remaining_data.sample(n=winner_num).reset_index(drop=True)
                            animation_placeholder.table(temp_winners)
                            time.sleep(0.05)  # 딜레이 시간 (초) 조정 가능
                        
                        # 최종 당첨자 선정
                        new_winners = remaining_data.sample(n=winner_num).reset_index(drop=True)
                        # Draw Name 추가
                        new_winners.insert(0, 'Draw Name', draw_name)
                        st.session_state.previous_winners = pd.concat([st.session_state.previous_winners, new_winners], ignore_index=True)
                        st.session_state.winners = new_winners.drop(columns=['Draw Name'])
                        st.session_state.current_round += 1
                        st.success("당첨자가 선정됐습니다!")
                        # 애니메이션 플레이스홀더에 최종 당첨자 표시
                        animation_placeholder.table(st.session_state.winners)
                else:
                    # 기존 당첨자 제외 옵션이 비활성화되었거나 이전 당첨자가 없을 때
                    if winner_num > total_entries:
                        st.error("당첨자 수가 전체 참여자 수보다 많을 수 없습니다.")
                    else:
                        # 애니메이션 효과: 빠르게 랜덤 당첨자 목록을 변경하며 "롤링"하는 효과
                        animation_steps = 20  # 애니메이션 단계 수
                        for i in range(animation_steps):
                            temp_winners = st.session_state.data.sample(n=winner_num).reset_index(drop=True)
                            animation_placeholder.table(temp_winners)
                            time.sleep(0.05)  # 딜레이 시간 (초) 조정 가능
                        
                        # 최종 당첨자 선정
                        new_winners = st.session_state.data.sample(n=winner_num).reset_index(drop=True)
                        # Draw Name 추가
                        new_winners.insert(0, 'Draw Name', draw_name)
                        st.session_state.previous_winners = pd.concat([st.session_state.previous_winners, new_winners], ignore_index=True)
                        st.session_state.winners = new_winners.drop(columns=['Draw Name'])
                        st.session_state.current_round += 1
                        st.success("당첨자가 선정됐습니다!")
                        # 애니메이션 플레이스홀더에 최종 당첨자 표시
                        animation_placeholder.table(st.session_state.winners)

            # 다운로드 준비는 기존과 동일하게 유지 (두 가지 형식으로 다운로드 가능하도록 수정)
            if not st.session_state.winners.empty:
                sanitized_draw_name = sanitize_filename(draw_name)
                
                # **CSV 다운로드 버튼**
                csv = st.session_state.winners.to_csv(index=False).encode('utf-8')
                download_filename_csv = f"{sanitized_draw_name}.csv"
                st.download_button(
                    label="당첨자 목록 다운로드 (CSV)",
                    data=csv,
                    file_name=download_filename_csv,
                    mime='text/csv',
                    key=f"download_{sanitized_draw_name}_result_csv"
                )
                
                # **엑셀 다운로드 버튼 추가**
                to_buffer = io.BytesIO()
                with pd.ExcelWriter(to_buffer, engine='openpyxl') as writer:
                    st.session_state.winners.to_excel(writer, index=False)
                to_buffer.seek(0)
                download_filename_excel = f"{sanitized_draw_name}.xlsx"
                st.download_button(
                    label="당첨자 목록 다운로드 (Excel)",
                    data=to_buffer,
                    file_name=download_filename_excel,
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    key=f"download_{sanitized_draw_name}_result_excel"
                )

        # **전체 당첨자 목록 다운로드 섹션 추가**
        if not st.session_state.previous_winners.empty:
            st.markdown("---")  # 구분선 추가
            st.header("전체 당첨자 목록 다운로드")
            
            # 전체 당첨자 목록을 하나의 DataFrame으로 정렬 (예: 추첨명 기준 정렬)
            all_winners = st.session_state.previous_winners.copy()
            all_winners = all_winners.sort_values(by='Draw Name')
            
            # 엑셀 다운로드
            to_buffer = io.BytesIO()
            with pd.ExcelWriter(to_buffer, engine='openpyxl') as writer:
                all_winners.to_excel(writer, index=False)
            to_buffer.seek(0)
            download_filename_excel = f"{sanitize_filename('전체 당첨자 목록')}.xlsx"
            st.download_button(
                label="전체 당첨자 목록 다운로드 (Excel)",
                data=to_buffer,
                file_name=download_filename_excel,
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                key="download_all_winners_excel"
            )
            
            # CSV 다운로드
            csv_all = all_winners.to_csv(index=False).encode('utf-8')
            download_filename_csv = f"{sanitize_filename('당첨자 목록')}.csv"
            st.download_button(
                label="전체 당첨자 목록 다운로드 (CSV)",
                data=csv_all,
                file_name=download_filename_csv,
                mime='text/csv',
                key="download_all_winners_csv"
            )
    else:
        st.info("데이터를 로드하려면 파일을 업로드하거나 URL을 입력하세요.")

if __name__ == "__main__":
    main()
