import json
import re
import os

def load_json_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_number(key):
    """
    'L1', 'L2' 등에서 숫자만 추출하여 정렬에 사용
    """
    m = re.search(r'\d+', key)
    if m:
        return int(m.group())
    return 0

# 원본 JSON 파일 경로
file = r"C:\Users\USER\Desktop\projects\eng_crawling\2022_error_log.json"
if os.path.exists(file):
    data = load_json_file(file)
else:
    data = {}

# 후보 출판사 리스트 (NE능률은 최종적으로 '능률'로 치환)
publisher_candidates = ["동아", "천재", "YBM", "NE능률", "교학사", "비상", "미래엔", "지학사", "금성", "능률"]

# 유효한 상위 키를 결정하는 키워드 리스트
valid_keywords = ["공통영어", "중2", "중3", "영어I", "영어II", "독해와작문", "영어권문화"]

# 새로운 결과를 담을 딕셔너리
new_data = {}

# 상위 키별 순회 (필터링: '심화' 또는 '다락원'이 포함되거나, 유효 키워드가 없으면 건너뛰기)
for top_key, top_value in data.items():
    if "심화" in top_key or "다락원" in top_key or not any(kw in top_key for kw in valid_keywords):
        continue

    new_inner = {}
    # 내부의 L 키들을 숫자 부분을 기준으로 정렬하여 L1부터 순서대로 처리
    for l_key in sorted(top_value.keys(), key=lambda k: extract_number(k)):
        content = top_value[l_key]
        # content가 dict이면 내부의 숫자 키들을 정렬 후 줄바꿈으로 합치기
        if isinstance(content, dict):
            combined = "\n".join(content[num_key] for num_key in sorted(content, key=lambda x: int(x)))
            new_inner[l_key] = combined
        else:
            new_inner[l_key] = content

    # --- 상위 키에서 추가 정보를 추출하는 부분 ---
    # 1. 학년 설정 (고등이면 '고2,3영어', 중2이면 '중2영어', 중3이면 '중3영어')
    if top_key.startswith("고등"):
        grade = "고2,3영어"
    elif top_key.startswith("중2"):
        grade = "중2영어"
    elif top_key.startswith("중3"):
        grade = "중3영어"
    elif top_key.startswith("공통영어"):
        grade = "고1영어"
    else:
        grade = ""

    # 2. 세부과목 및 출판사/저자 정보 추출
    subject = ""         # 고등의 경우 세부과목 (매핑 적용)
    publisher_info = ""  # 출판사와 저자 정보 (문자열)

    if top_key.startswith("고등"):
        # 고등의 경우 형식은 "고등_<세부과목>(출판사저자)"이다.
        try:
            parts = top_key.split("_", 1)
            if len(parts) > 1:
                # 두 번째 부분에서 괄호 전의 세부과목과 괄호 안의 출판사+저자 정보를 분리
                second_part = parts[1]
                match = re.search(r'\((.*?)\)', second_part)
                if match:
                    publisher_info = match.group(1)
                    subject_raw = second_part.split("(")[0]
                else:
                    subject_raw = second_part
                    publisher_info = ""
                # subject 매핑
                if subject_raw == "영어I":
                    subject = "영어1"
                elif subject_raw == "영어II":
                    subject = "영어2"
                elif subject_raw == "영어권문화":
                    subject = "영어권 문화"
                elif subject_raw == "독해와작문":
                    subject = "영어 독해와 작문"
                else:
                    subject = subject_raw
            else:
                subject = ""
                publisher_info = ""
        except Exception as e:
            subject = ""
            publisher_info = ""
    elif top_key.startswith("공통영어"):
        try:
            parts = top_key.split("_", 1)
            if len(parts) > 1:
                subject = parts[0]
                publisher_info = parts[1]
            else:
                subject = ""
                publisher_info = ""
        except Exception as e:
            subject = ""
            publisher_info = ""
    else:
        # 중등의 경우 형식은 "중3_지학사양현권" 등, 언더바 뒤의 전체가 출판사+저자 정보임
        parts = top_key.split("_", 1)
        if len(parts) > 1:
            publisher_info = parts[1]
        else:
            publisher_info = ""

    # 3. 출판사와 저자 분리
    publisher = ""
    author = ""
    for cand in publisher_candidates:
        if publisher_info.startswith(cand):
            publisher = "능률" if cand == "NE능률" else cand
            author = publisher_info[len(cand):]  # 후보 이름 길이 이후의 문자열이 저자
            break
    publisher = publisher.strip()
    author = author.strip()

    # 4. 새롭게 추가할 키들을 inner dict에 추가
    new_inner["학년"] = grade
    # 고등은 세부과목 추가, 중등은 빈 문자열 처리
    new_inner["세부과목"] = subject if top_key.startswith("고등") or top_key.startswith("공통영어") else ""
    new_inner["출판사"] = publisher
    new_inner["저자"] = author

    # 최종 결과에 추가
    new_data[top_key] = new_inner

# 결과를 새로운 JSON 파일로 저장
output_file = r"C:\Users\USER\Desktop\projects\eng_crawling\2022_results_organize.json"
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(new_data, f, ensure_ascii=False, indent=4)

print("Filtered JSON data saved to:", output_file)