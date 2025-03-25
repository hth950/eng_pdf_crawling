import json
import re
import os

def load_json_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

# 원본 JSON 파일 경로
file = "/data/eduspace-ai-server/tests/test/merged.json"
if os.path.exists(file):
    data = load_json_file(file)
else:
    data = {}

# 유효한 상위 키를 결정하는 키워드 리스트
valid_keywords = ["중2", "중3", "영어I", "영어II", "독해와작문", "영어권문화"]

def check_missing_numbers(content_dict):
    """
    content_dict 내부의 키 중 숫자로 변환 가능한 키들을 추출하여,
    1부터 최대 숫자까지 누락된 키(숫자)를 문자열 리스트로 반환한다.
    """
    numeric_keys = []
    for key in content_dict.keys():
        try:
            num = int(key)
            numeric_keys.append(num)
        except ValueError:
            continue  # 숫자로 변환되지 않는 키는 무시
    if not numeric_keys:
        return []  # 숫자 키가 하나도 없으면 빈 리스트 반환
    max_num = max(numeric_keys)
    missing = [str(i) for i in range(1, max_num + 1) if i not in numeric_keys]
    return missing

# 상위 키 순회 시, valid_keywords에 해당하는 키워드가 포함된 경우에만 처리
for top_key, top_value in data.items():
    if not any(kw in top_key for kw in valid_keywords):
        continue
    if "심화" in top_key or "다락원" in top_key or "영어II" in top_key:
        continue

    # 내부 항목(L 키) 순회
    for lesson_key, content in top_value.items():
        # lesson_key가 "L1" 또는 "Special Lesson"으로 시작하는 경우 처리
        if lesson_key.startswith("L"):
            if isinstance(content, dict):
                missing = check_missing_numbers(content)
                if missing:
                    print(f"상위 키 '{top_key}'의 '{lesson_key}'에서 누락된 번호: {missing}")
            else:
                print(f"상위 키 '{top_key}'의 '{lesson_key}'는 dict가 아닙니다. (내용 타입: {type(content)})")