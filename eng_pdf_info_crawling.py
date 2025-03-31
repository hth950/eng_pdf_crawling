import os
import json
import re
import time
import glob
import PyPDF2
from multiprocessing import Pool, cpu_count
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 결과와 오류를 저장할 JSON 파일 경로
RESULTS_JSON_FILE = "2022_results.json"
ERROR_LOG_JSON_FILE = "2022_error_log.json"


def load_data(file_path):
    """지정한 JSON 파일이 있으면 불러오고, 없으면 빈 딕셔너리를 반환합니다."""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}
    return data


def save_data(data, file_path):
    """딕셔너리 데이터를 지정한 JSON 파일로 저장합니다."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def safe_quit(driver):
    """드라이버 종료 시 예외를 잡고, 종료 후 5초 대기하여 포트가 해제되도록 합니다."""
    try:
        driver.quit()
    except Exception as e:
        print("safe_quit() 오류:", e)
    time.sleep(5)


def init_driver():
    """새로운 ChromeDriver 인스턴스를 생성하고 WebDriverWait 객체를 반환합니다."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 15)
    return driver, wait


def process_sentence(sentence, driver, wait, data):
    """
    주어진 문장을 검색어로 하여 Selenium을 통해 결과를 처리하고,
    추출된 정보를 data 딕셔너리에 누적 저장합니다.

    결과 페이지에서 검색어와 p.desc_txt span 내부의 텍스트가 일치하는지 확인합니다.
    일치하지 않거나 연결 오류가 발생하면 최대 3회까지 드라이버를 안전하게 종료 후 재시작하여 재검색합니다.
    """
    url = "https://www.worksheetmaker.co.kr/user20/dataTexts/list.do#noback"
    max_attempts = 3
    attempt = 0

    while attempt < max_attempts:
        try:
            driver.get(url)
            # 'popup_search' 영역 로딩 대기
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "popup_search")))

            # 검색 입력란 로딩 대기 및 검색어 입력
            search_input = wait.until(
                EC.presence_of_element_located((By.ID, "searchText"))
            )
            search_input.clear()
            search_input.send_keys(sentence)

            # 검색 버튼 클릭
            search_button = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//div[contains(@class, 'popup_search')]//button[contains(@class, 'btn') and contains(@onclick, 'MainMgr.search')]",
                    )
                )
            )
            search_button.click()

            # 결과 페이지 로딩 대기
            time.sleep(3)

            # 결과 페이지에서 p.desc_txt span 내부의 텍스트 확인
            result_span = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "p.desc_txt span"))
            )
            result_text = result_span.text.strip()

            if result_text == sentence:
                print(f"[성공] 검색어 '{sentence}'와 결과 텍스트 일치")
                break  # 정상 처리 시 while 탈출
            else:
                attempt += 1
                print(
                    f"[재시도 {attempt}/{max_attempts}] 결과 텍스트 '{result_text}' ≠ 검색어 '{sentence}'"
                )
                safe_quit(driver)
                driver, wait = init_driver()
        except Exception as e:
            # 연결 오류(예: WinError 10061) 등 발생 시
            attempt += 1
            print(f"[재시도 {attempt}/{max_attempts}] 예외 발생: {e}")
            safe_quit(driver)
            driver, wait = init_driver()

    # 결과 페이지에서 테이블들 추출 후 정보 수집
    try:
        tables = driver.find_elements(
            By.XPATH,
            "//div[contains(@class, 'hor_tb pop_tb')]//table[contains(@class, 'tb_mt_0')]",
        )
        if not tables:
            print(f"[검색결과 없음] 검색어: {sentence}")
            return driver, wait
        for table in tables:
            try:
                source_td = table.find_element(
                    By.XPATH, ".//tr[th[normalize-space(text())='지문출처']]/td"
                )
                source_text = source_td.text
                match = re.search(
                    r"교과서명,\s*레슨,\s*본문번호\s*:\s*([^\n\r]+)", source_text
                )
                if match:
                    extracted_info = match.group(1).strip().split(",")
                    if len(extracted_info) >= 3:
                        key1 = extracted_info[0].strip()  # 학년, 출판사정보
                        key2 = extracted_info[1].strip()  # 단원명
                        key3 = extracted_info[2].strip()  # 본문번호
                        try:
                            english_td = table.find_element(
                                By.XPATH,
                                ".//tr[th[normalize-space(text())='영어 지문']]/td",
                            )
                            english_text = english_td.text
                            print(f"검색어: {sentence} → {key1} > {key2} > {key3}")
                            # 결과 누적 저장 (동일 키는 덮어쓰기)
                            if key1 not in data:
                                data[key1] = {}
                            if key2 not in data[key1]:
                                data[key1][key2] = {}
                            data[key1][key2][key3] = english_text
                        except Exception as e:
                            print("영어 지문 추출 오류:", e)
                    else:
                        print("추출된 정보 항목 부족 for 검색어:", sentence)
                else:
                    print("교과서 정보 미발견 for 검색어:", sentence)
            except Exception as e:
                print("지문출처 추출 오류:", e)
    except Exception as e:
        print("테이블 검색 중 오류:", e)

    return driver, wait


def extract_sentences_from_pdf(pdf_path):
    """
    PDF 파일에서 텍스트를 추출한 후,
    한글 제거, 문장 분리 및 전처리를 수행하여 문장 리스트를 반환합니다.

    만약 문장에 ':'가 있다면, ':' 이후의 부분만 사용하며,
    문장이 오직 영어 알파벳, 공백, '.', ',', '\'', '\"', ':' 만 포함하는 경우에만 반환합니다.
    """
    sentences = []
    allowed_pattern = re.compile(r'^[A-Za-z\s\.\,\':"]+$')
    with open(pdf_path, "rb") as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for i, page in enumerate(pdf_reader.pages):
            text = page.extract_text()
            if not text:
                continue
            text = (
                text.replace("‘", "'")
                .replace("’", "'")
                .replace("“", '"')
                .replace("”", '"')
            )
            text = re.sub(r"[ㄱ-ㅎ가-힣]+", "", text)
            page_sentences = re.split(r"[\.!?\n]+\s*", text)
            processed_sentences = []
            for s in page_sentences:
                s = s.strip()
                if ":" in s:
                    s = s.split(":", 1)[1].strip()
                if not s or s.count(" ") <= 3:
                    continue
                if allowed_pattern.fullmatch(s):
                    processed_sentences.append(s)
            sentences.extend(processed_sentences)
            print(
                f"----------- {i+1} 페이지에서 추출된 문장 수: {len(processed_sentences)} -----------"
            )
    return sentences


def merge_results(dict1, dict2):
    """
    두 개의 결과 딕셔너리를 재귀적으로 병합합니다.
    같은 키가 존재하면 dict2의 값으로 덮어씁니다.
    """
    for key, value in dict2.items():
        if key in dict1 and isinstance(dict1[key], dict) and isinstance(value, dict):
            merge_results(dict1[key], value)
        else:
            dict1[key] = value
    return dict1


def process_pdf(pdf_path):
    """
    하나의 PDF 파일을 처리하여 검색 결과와 해당 PDF 처리 중 발생한 오류 목록을 딕셔너리로 반환합니다.
    """
    print(f"PDF 처리 시작: {pdf_path}")
    data = {}
    error_log = []  # 해당 PDF 파일 처리 중 발생한 오류 기록 (검색어와 에러 메시지)
    sentences = extract_sentences_from_pdf(pdf_path)
    driver, wait = init_driver()
    for sentence in sentences:
        try:
            driver, wait = process_sentence(sentence, driver, wait, data)
        except Exception as e:
            error_entry = {
                "pdf_file": pdf_path,
                "search_term": sentence,
                "error": str(e),
            }
            error_log.append(error_entry)
            print(f"[오류 기록] {error_entry}")
            # 오류 발생 시 해당 문장은 건너뛰고 계속 진행
    safe_quit(driver)
    print(f"PDF 처리 종료: {pdf_path}")
    return {"data": data, "errors": error_log}


def process_all_pdfs(folder_path):
    """
    주어진 폴더 및 하위 폴더 내의 모든 PDF 파일을 병렬로 처리합니다.
    각 PDF의 결과와 오류 기록을 병합하여 최종 결과 딕셔너리를 반환합니다.
    """
    pdf_files = glob.glob(os.path.join(folder_path, "**/*.pdf"), recursive=True)
    print("처리할 PDF 파일 수:", len(pdf_files))

    results = {}
    all_errors = []  # 모든 PDF의 오류 기록을 모음
    with Pool(processes=6) as pool:
        pdf_results = pool.map(process_pdf, pdf_files)
        for res in pdf_results:
            merge_results(results, res["data"])
            all_errors.extend(res["errors"])
    return {"data": results, "errors": all_errors}


if __name__ == "__main__":
    # PDF 파일들이 들어있는 폴더 경로 (본인 환경에 맞게 수정)
    PDF_FOLDER = r"./2022_test"

    # 폴더 및 하위 폴더 내 모든 PDF 파일 병렬 처리
    final_result = process_all_pdfs(PDF_FOLDER)

    # 최종 결과와 오류 기록을 JSON 파일에 저장
    save_data(final_result["data"], RESULTS_JSON_FILE)
    save_data(final_result["errors"], ERROR_LOG_JSON_FILE)

    print("\n최종 결과 JSON 데이터:")
    print(json.dumps(final_result["data"], ensure_ascii=False, indent=4))
    print("\n오류 기록 JSON 데이터:")
    print(json.dumps(final_result["errors"], ensure_ascii=False, indent=4))
