import os
import asyncio
import csv
import json
import re
from dotenv import load_dotenv
from typing import Optional, List

# 환경변수 로드 및 DB 연결 URL 생성
load_dotenv()
OCI_DB_HOST = os.getenv("OCI_DB_HOST")
OCI_DB_USER = os.getenv("OCI_DB_USER")
OCI_DB_PASSWORD = os.getenv("OCI_DB_PASSWORD")
OCI_DB_PORT = os.getenv("OCI_DB_PORT")
OCI_DB_NAME = os.getenv("OCI_DB_NAME_TH")
db_url = f"mysql+aiomysql://{OCI_DB_USER}:{OCI_DB_PASSWORD}@{OCI_DB_HOST}:{OCI_DB_PORT}/{OCI_DB_NAME}"

# DBManager와 ORM 모델 import (실제 파일 경로에 맞게 조정)
from DB import DatabaseManager, Tag, Textbook, TextbookPassage, TextbookPassageTagBind  # 미리 정의된 비동기 DatabaseManager 클래스

def normalize_text(text: str) -> str:
    """
    주어진 텍스트에서 알파벳 이외의 문자를 모두 제거하고 소문자로 변환
    """
    return re.sub(r'[^A-Za-z0-9]', '', text).lower()

# ----------------------------------------------------------------------------
# helper 함수들: get_or_create_* 함수들은 기존 데이터가 있으면 리턴, 없으면 생성합니다.
# ----------------------------------------------------------------------------

async def get_or_create_tag(db_manager, name: str, category: str, parent_id: Optional[int], desc: str) -> Tag:
    # 대단원(category가 "대단원")인 경우, parent_id가 있을 때
    if category == "대단원" and parent_id is not None:
        # 동일 parent_id와 category("대단원")를 가진 모든 태그를 조회
        if desc:
            filters = {"category": category, "parent_id": parent_id, "desc": desc}
        else:
            filters = {"category": category, "parent_id": parent_id}
        existing_tags: List[Tag] = await db_manager.get_all(Tag, filters)
        normalized_input = normalize_text(name)
        for tag in existing_tags:
            # 각 기존 태그의 name을 normalize하여 비교 (특수문자, 띄어쓰기 제거, 소문자 변환)
            if normalize_text(tag.name) == normalized_input:
                return tag
    else:
        # 대단원이 아니거나 parent_id가 없는 경우엔 기존의 exact match 방식 사용
        filters = {"name": name, "category": category, "parent_id": parent_id}
        tags: List[Tag] = await db_manager.get_all(Tag, filters)
        if tags:
            return tags[0]

    # 동일한 태그가 없는 경우, 새로 생성
    if desc:
        tag_data = {"name": name, "category": category, "parent_id": parent_id, "desc": desc}
    else:
        tag_data = {"name": name, "category": category, "parent_id": parent_id, "desc": None}
    tag = await db_manager.create_entry(Tag, tag_data)
    return tag

async def get_or_create_textbook(db_manager, data: dict) -> Textbook:
    filters = {
        "name": data["name"],
        "publisher": data["publisher"],
        "author": data["author"],
        "revision_year": data["revision_year"],
        "subject": data["subject"],
        "level": data["level"],
    }
    textbooks: List[Textbook] = await db_manager.get_all(Textbook, filters)
    if textbooks:
        return textbooks[0]
    textbook = await db_manager.create_entry(Textbook, data)
    return textbook

async def get_or_create_textbook_passage(db_manager, textbook_id: int, passage_text: str) -> TextbookPassage:
    filters = {"textbook_id": textbook_id, "passage": passage_text}
    passages: List[TextbookPassage] = await db_manager.get_all(TextbookPassage, filters)
    if passages:
        return passages[0]
    data = {
        "textbook_id": textbook_id,
        "passage": passage_text,
        "article": None,
        "author": None,
        "additional_info": None,
    }
    passage = await db_manager.create_entry(TextbookPassage, data)
    return passage

async def get_or_create_textbook_passage_tag_bind(db_manager, textbook_passage_id: int, tag_id: int) -> TextbookPassageTagBind:
    filters = {"textbook_passage_id": textbook_passage_id, "tag_id": tag_id}
    binds: List[TextbookPassageTagBind] = await db_manager.get_all(TextbookPassageTagBind, filters)
    if binds:
        return binds[0]
    data = {"textbook_passage_id": textbook_passage_id, "tag_id": tag_id}
    bind_entry = await db_manager.create_entry(TextbookPassageTagBind, data)
    return bind_entry

# ----------------------------------------------------------------------------
# 메인 처리 함수: JSON/CSV 파일 읽고 조건에 맞게 DB에 삽입
# ----------------------------------------------------------------------------

async def process_files(json_file_path: str, csv_file_path: str, db_url: str):
    # 1. JSON 파일 읽기
    with open(json_file_path, encoding="utf-8") as f:
        json_data = json.load(f)

    # 2. CSV 파일 읽기 – 각 행을 dict로 읽어서 리스트에 저장
    csv_rows = []
    with open(csv_file_path, encoding="euc-kr", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # 각 컬럼의 좌우 공백 제거
            csv_rows.append({k: v.strip() for k, v in row.items()})

    # 3. DBManager 인스턴스 생성 및 DB 연결
    db_manager = DatabaseManager(db_url=db_url)
    await db_manager.connect()

    # 4. JSON의 최상위 키별로 처리 (예: "중3_YBM박준언", "고등_영어II(금성최인철)" 등)
    for top_key, content in json_data.items():
        # JSON 내 기본 정보
        grade = content.get("학년", "").strip()  # 예: "중3영어" 또는 "고2,3영어"
        subject_detail = content.get("세부과목", "").strip()  # 값이 없으면 빈 문자열
        publisher = content.get("출판사", "").strip()
        author = content.get("저자", "").strip()
        # 출판사 태그 이름: "출판사(저자)" 형태 (출판사와 저자 모두 있을 때)
        pub_tag_name = f"[2022개정]{publisher}({author})" if publisher and author else ""

        # ① Tag 삽입
        # - 학년 태그 (category="학년")
        grade_tag = await get_or_create_tag(db_manager, name=grade, category="학년", parent_id=None)
        # - 세부과목 태그 (있다면; category="세부과목", parent=학년 태그)
        subject_tag = None
        # if subject_detail:
        #     subject_tag = await get_or_create_tag(db_manager, name=subject_detail, category="세부과목", parent_id=grade_tag.id)
        # - 출판사 태그 (있다면; category="출판사")
        publisher_tag = None
        if pub_tag_name:
            parent_for_pub = subject_tag.id if subject_tag else grade_tag.id
            publisher_tag = await get_or_create_tag(db_manager, name=pub_tag_name, category="출판사", parent_id=parent_for_pub)

        # ② CSV 조건에 따른 region 판별
        # 예: "중2영어" → path1="중2", "중3영어" → path1="중3", "고2,3영어" → path1이 "고2" 또는 "고3"
        if "중2영어" in grade:
            region = "중2"
        elif "중3영어" in grade:
            region = "중3"
        elif "고" in grade or "고2,3영어" in grade:
            region = "고"  # 실제 CSV에서는 "고2" 또는 "고3"로 판별
        else:
            region = None

        # ③ JSON의 "L"로 시작하는 키(대단원)를 찾아 처리
        lesson_keys = [k for k in content.keys() if k.startswith("L")]
        lesson_tag_map = {}  # { L키: 대단원 태그 }
        for lkey in lesson_keys:
            lesson_text = content[lkey].strip()
            # 대단원 태그의 이름은 CSV의 file 컬럼을 이용하여 가공함.
            if lkey.startswith("LSpecial Lesson"):
                is_special = True
                m = re.match(r"LSpecial Lesson\s*(\d+)", lkey)
                if m:
                    lesson_number = m.group(1)
                    prefix = f"Special Lesson {lesson_number}"
                else:
                    lesson_number = None
                    prefix = "Special Lesson"
            else:
                is_special = False
                m = re.match(r"L(\d+)", lkey)
                if m:
                    lesson_number = m.group(1)
                    prefix = f"Lesson {lesson_number}"
                else:
                    continue

            # CSV 파일에서 현재 JSON 레코드에 맞는 행(row) 찾기
            csv_match = None
            for row in csv_rows:
                # region 처리
                if region in ["중2", "중3"]:
                    if row.get("path1") != region:
                        continue
                    # 중등의 경우: path2는 pub_tag_name과 동일하고, path3는 빈 값이어야 함
                    if row.get("path2") != pub_tag_name or row.get("path3"):
                        continue
                elif region == "고":
                    if row.get("path1") not in ["고1", "고2", "고3"]:
                        continue
                    # 고등은 세부과목이 있으므로: path2는 subject_detail, path3는 pub_tag_name이어야 함
                    if row.get("path1") in ["고1","고2", "고3"]:
                        if row.get("path2") != subject_detail or row.get("path3") != pub_tag_name:
                            continue
                else:
                    continue

                file_val = row.get("file", "")
                # CSV의 file 값과 비교할 때, 특수문자 제거 후 소문자로 변환하여 비교합니다.
                if not normalize_text(file_val).startswith(normalize_text(prefix)):
                    continue

                if is_special:
                    lesson_tag_name = file_val  # 특수 Lesson은 그대로 사용
                else:
                    remainder = file_val[len(prefix):].strip()
                    lesson_tag_name = f"{lesson_number}. {remainder}" if remainder else f"{lesson_number}."
                csv_match = row
                break

            if not csv_match:
                print(f"[Warning] {top_key}의 {lkey}에 대해 CSV 매칭 row를 찾지 못했습니다.")
                continue

            # 대단원 태그 삽입 – parent는 출판사 태그가 있으면 그 id, 없으면 학년 태그 id 사용
            parent_for_lesson = publisher_tag.id if publisher_tag else grade_tag.id
            lesson_tag = await get_or_create_tag(db_manager, name=lesson_tag_name, category="대단원", parent_id=parent_for_lesson, desc=None)
            lesson_tag_map[lkey] = lesson_tag

        # ④ Textbook, TextbookPassage 삽입
        # Textbook의 name은 세부과목이 있으면 그 값, 없으면 학년 값 사용
        textbook_name = subject_detail if subject_detail else grade
        # level: 학년에 "중"이 있으면 "middle", "고"가 있으면 "high"
        if "중" in grade:
            level = "middle"
        elif "고" in grade:
            level = "high"
        else:
            level = None
        textbook_data = {
            "name": textbook_name,
            "publisher": publisher,
            "author": author,
            "revision_year": "22",
            "subject": "english",
            "level": level,
        }
        textbook = await get_or_create_textbook(db_manager, textbook_data)

        # JSON의 각 L키에 해당하는 passage 텍스트로 TextbookPassage 생성
        passage_map = {}  # { lkey: TextbookPassage 객체 }
        for lkey in lesson_keys:
            passage_text = content[lkey].strip()
            passage = await get_or_create_textbook_passage(db_manager, textbook.id, passage_text)
            passage_map[lkey] = passage

        # ⑤ TextbookPassage와 태그를 바인딩: 각 passage에 대해 (학년, 세부과목, 출판사, 해당 대단원 태그)를 연결
        for lkey, passage in passage_map.items():
            tag_list = [grade_tag]
            if subject_tag:
                tag_list.append(subject_tag)
            if publisher_tag:
                tag_list.append(publisher_tag)
            if lkey in lesson_tag_map:
                tag_list.append(lesson_tag_map[lkey])
            for tag in tag_list:
                await get_or_create_textbook_passage_tag_bind(db_manager, passage.id, tag.id)

    # 모든 처리가 끝나면 DB 연결 종료
    await db_manager.disconnect()

# ----------------------------------------------------------------------------
# 메인 함수: DBManager를 환경변수로 설정한 DB URL과 함께 실행
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    # JSON_FILE = "/data/eduspace-ai-server/tests/test/eng_textbook_results_filtered_test.json"  # JSON 파일 경로 지정
    JSON_FILE = r"C:\Users\USER\Desktop\projects\eng_crawling\2022_results_organize.json"  # JSON 파일 경로 지정
    CSV_FILE = r"C:\Users\USER\Desktop\projects\eng_crawling\eng_pdf_crawling\고1 22개정 영어 본문-2.csv"    # CSV 파일 경로 지정

    asyncio.run(process_files(JSON_FILE, CSV_FILE, db_url))
