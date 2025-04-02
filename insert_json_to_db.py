import asyncio
import json
import os

from dotenv import load_dotenv


load_dotenv()
OCI_DB_HOST = os.getenv("DB_HOST")
OCI_DB_USER = os.getenv("DB_USER")
OCI_DB_PASSWORD = os.getenv("DB_PASSWORD")
OCI_DB_PORT = os.getenv("DB_PORT")
OCI_DB_NAME = os.getenv("DB_NAME")
db_url = f"mysql+aiomysql://{OCI_DB_USER}:{OCI_DB_PASSWORD}@{OCI_DB_HOST}:{OCI_DB_PORT}/{OCI_DB_NAME}"

from DB import (
    DatabaseManager,
    Textbook,
    TextbookPassage,
)


def load_json_file(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


async def insert_json_to_db(json_data):
    # JSON 데이터를 DB에 삽입하는 비동기 함수
    # 실제 DB 삽입 로직을 여기에 구현합니다.
    # 예시로 print 문을 사용합니다.
    db_manager = DatabaseManager(db_url=db_url)
    await db_manager.connect()
    for p_id, p_value in json_data.items():
        # 상위 키별 순회
        content = p_value.get("content")
        if content:
            if len(content) <= 1:
                print("------------------------------------")
                print(f"{p_id} is unavailable")
            else:
                sorted_keys = sorted(content.keys(), key=lambda x: int(x))
                if sorted_keys[-1] != str(len(sorted_keys)):
                    print("------------------------------------")
                    print(f"{p_id} is unavailable")

            # for key, value in content.items():
            #     # 하위 키별 순회
            #     print(f"Processing {p_id} - {key}: {value}")
    await db_manager.disconnect()

    # print(f"Inserting data into DB: {json_data}")


if __name__ == "__main__":

    async def main():
        # PDF 파일들이 들어있는 폴더 경로 (본인 환경에 맞게 수정)
        organized_json_path = "./2022_results_organize.json"
        data = {}
        if os.path.exists(organized_json_path):
            data = load_json_file(organized_json_path)

        # 폴더 및 하위 폴더 내 모든 PDF 파일 병렬 처리
        final_result = await insert_json_to_db(data)

    asyncio.run(main())
