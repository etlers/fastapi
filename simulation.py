# -*- coding: utf-8 -*-
"""
    당일 디비에 적재된 현재일자의 정보로 시뮬레이션 갭을 변경하며 손익을 확인할 수 있다.
"""

import pandas as pd
import pymysql
import matplotlib.pyplot as plt
import yaml, datetime

# 조회하고자 하는 모든 종목 리스트 추출 저장
with open('config.yaml', encoding='UTF8') as f:
    kiwoom_cfg = yaml.load(f, Loader=yaml.FullLoader)
    # 종목코드
    jongmok_code = kiwoom_cfg["jongmok_code"]
    # 디비 정보
    host_ip = kiwoom_cfg["stock_conn"]["stock_ip"]
    host_port = kiwoom_cfg["stock_conn"]["stock_port"]
    db_name = kiwoom_cfg["stock_conn"]["stock_db"]
    user_name = kiwoom_cfg["stock_conn"]["stock_user"]
    user_pswd = kiwoom_cfg["stock_conn"]["stock_pswd"]
    # 시뮬레이션
    seed_money = kiwoom_cfg["simulation"]["seed_money"]
    # 최초 설정 금액
    first_price = kiwoom_cfg["simulation"]["first_price"]
    # 시뮬레이션 리스트
    list_gap = kiwoom_cfg["simulation"]["list_gap"]

now_dt = datetime.date.today()
DT = str(now_dt.year) + str(now_dt.month).zfill(2) + str(now_dt.day).zfill(2)

def execute_logic(buy_gap, sell_gap, stop_loss):
    list_db_price = []     
    order_cnt = 0
    buy_price = 0
    std_price = 0       

    def make_list_from_db():        
        # MySQL Connection 연결
        conn = pymysql.connect(
            host=host_ip, 
            #port=host_port,
            user=user_name, 
            password=user_pswd,
            db=db_name, 
            charset='utf8')
        
        # Connection 으로부터 Cursor 생성
        curs = conn.cursor()
        # SQL문 생성
        sql = "select NOW_PRC from stock.TB_STC_PRC where dt = date_format(now(), '%Y%m%d') and stc_cd = '" + jongmok_code + "' order by TM "
        #sql = "select NOW_PRC from stock.TB_STC_PRC_210326 where dt = '20210326' and stc_cd = '" + jongmok_code + "' order by TM "
        # SQL문 실행
        curs.execute(sql)

        # 데이타 Fetch
        rows = curs.fetchall()
        for row in rows:
            list_db_price.append(row[0])
        
        # Connection 닫기
        conn.close()

    # 리스트에서 빼서 줌
    def get_now_price_from_db():
        now_price = list_db_price[0]
        list_db_price.pop(0)
        return now_price

    make_list_from_db()

    # 매수(1), 매도(2) 구분. 처음에는 무조건 매수가 됨
    order_div = 1
    # 시뮬레이션 결과 리스트
    list_simulation = []
    cnt = 0

    amount_sum = 0
    fee_sum = 0
    for idx in range(len(list_db_price)):
        now_price = get_now_price_from_db()
        cnt += 1
        
        if idx == 0:
            # 최초 기준금액 설정
            std_price = now_price + buy_gap
        #####################################################################################################
        # 가장 최근 가격과 최소값 + 갭 둘을 비교
        #####################################################################################################
        list_temp = []
        # 매수의 경우,
        if order_div == 1:
            # 기준가격과 현재 가격이 같으면 매수
            if now_price >= std_price:
                # 수량 계산. 증액해 계산
                order_cnt = int(seed_money / (now_price + buy_gap))
                list_temp.append("Buy")
                list_temp.append(now_price)
                list_temp.append(order_cnt)
                amount_sum += now_price * order_cnt * -1
                list_temp.append(now_price * order_cnt * -1)
                fee_sum += round(now_price * order_cnt * 0.00015, 0)
                list_temp.append(round(now_price * order_cnt * 0.00015, 0))
                list_simulation.append(list_temp)
                order_div = 2
                std_price = now_price - sell_gap
            # 현재가격이 기준 가격보다 적으면 기준 가격을 변경
            elif now_price + buy_gap < std_price:
                std_price = now_price + buy_gap
        # 매도인 경우 현재가격이 기준 가격보다 크면 기준 가격을 변경
        else:
            # 현재 가격이 손절가 아래로 내려가는 경우 바로 매도
            if (now_price <= buy_price - stop_loss):
                list_temp.append("Sell")
                list_temp.append(now_price)
                list_temp.append(order_cnt)
                amount_sum += now_price * order_cnt
                list_temp.append(now_price * order_cnt)
                fee_sum += round(now_price * order_cnt * 0.00015, 0)
                list_temp.append(round(now_price * order_cnt * 0.00015, 0))
                list_simulation.append(list_temp)
                order_cnt = 0
                order_div = 1
                std_price = now_price + buy_gap
            # 기준가격과 현재 가격이 같으면 매도
            elif now_price <= std_price:
                list_temp.append("Sell")
                list_temp.append(now_price)
                list_temp.append(order_cnt)
                amount_sum += now_price * order_cnt
                list_temp.append(now_price * order_cnt)
                fee_sum += round(now_price * order_cnt * 0.00015, 0)
                list_temp.append(round(now_price * order_cnt * 0.00015, 0))
                list_simulation.append(list_temp)
                order_cnt = 0
                order_div = 1
                std_price = now_price + buy_gap
            # 현재가격이 기준 가격보다 크면 기준 가격을 변경
            elif now_price - sell_gap > std_price:
                std_price = now_price - sell_gap
        #####################################################################################################
    # 마지막 매수 수량이 존재하면 매도
    if order_cnt > 0:
        list_temp.append("Sell")
        list_temp.append(now_price)
        list_temp.append(order_cnt)
        amount_sum += now_price * order_cnt
        list_temp.append(now_price * order_cnt)
        fee_sum += round(now_price * order_cnt * 0.00015, 0)
        list_temp.append(round(now_price * order_cnt * 0.00015, 0))
        list_simulation.append(list_temp)

    list_temp = []    
    list_temp.append("RESULT")
    # 최종 수익 = 매수매도 합계 - 수수료 합계
    list_temp.append(int(amount_sum - fee_sum))
    list_temp.append(0)
    # 매수 매도 합계
    list_temp.append(amount_sum)
    # 수수료 합계
    list_temp.append(int(fee_sum))
    list_simulation.append(list_temp)
    # CSV 파일 생성    
    df_simulation = pd.DataFrame(list_simulation, columns=["구분","단가(손익)","수량","금액","수수료"])
    excel_file = DT + "_simul_" + str(buy_gap) + "_" + str(sell_gap) + "_" + str(stop_loss) + ".csv"
    df_simulation.to_csv(excel_file, index=False, encoding="utf-8-sig")

    # 그래프 표시
    plt.plot(list_db_price)
    plt.show()

for gap in list_gap:
    # 시뮬레이션 - 메수갭, 매도갭, 손절갭
    execute_logic(gap[0], gap[1], gap[2])
