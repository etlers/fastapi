from selenium import webdriver
import time
import json
import sys
import urllib.request as req

from fake_useragent import UserAgent

#sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
#sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

# Fake Header 정보
ua = UserAgent()

# 헤더 선언
headers = {
    'User-Agent': ua.ie,
    'referer': 'https://finance.daum.net/'
}

# 다음 주식 요청 URL
#url = "https://finance.daum.net/api/search/ranks?limit=10"
#url = "http://finance.daum.net/api/charts/A122630/days?limit=1&adjusted=true"

# print(request.get_method())   #Post or Get 확인
# print(request.get_full_url()) #요청 Full Url 확인



def get_data():
    url = "http://finance.daum.net/api/charts/A122630/days?limit=1&adjusted=true"
    # 요청
    res = req.urlopen(req.Request(url, headers=headers)).read().decode('utf-8')

    # 응답 데이터 확인(Json Data)
    # print('res', res)

    # 응답 데이터 str -> json 변환 및 data 값 저장
    data = json.loads(res)
    # 중간 확인
    

    driver = webdriver.Chrome()
    driver.get(url)
    driver.close()

    return data["data"][0]["tradePrice"], data["data"][0]["tradeTime"], data["data"][0]["date"]

for _ in range(10):
    print(get_data())
    time.sleep(1)
