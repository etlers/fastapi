# -*- coding: utf-8 -*-
"""
    체결정보요청 데몬

    * 지정한 시간 동안만 데몬이 떠 있는다. 매일 띄워줘야 함. 윈도우 스케쥴 기능 이용 필요
    * 지정한 분초 동안만 수행. 지정한 분초 구간에 맞질 않으면 초 단위로 체크만 한다.
"""
import datetime
import sys
import os
import time
import threading
from threading import Event, Lock
import logging
from logging import FileHandler

from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QObject
from PyQt5.QtCore import QThread
from PyQt5.QtCore import QEventLoop
from PyQt5.QtWidgets import QApplication

import numpy as np
import pandas as pd

import util
import yaml
import pymysql

# 조회하고자 하는 모든 종목 리스트 추출 저장
with open('config.yaml', encoding='UTF8') as f:
    kiwoom_cfg = yaml.load(f, Loader=yaml.FullLoader)
    # 종목코드
    jongmok_code = kiwoom_cfg["list_jongmok_code"]
    # 수행 시간
    run_day_start = kiwoom_cfg["run_day"][0]
    run_day_end = kiwoom_cfg["run_day"][1]
    run_minute_start = kiwoom_cfg["run_minute"][0]
    run_minute_end = kiwoom_cfg["run_minute"][1]
    # 디비 정보
    host_ip = kiwoom_cfg["stock_conn"]["stock_ip"]
    host_port = kiwoom_cfg["stock_conn"]["stock_port"]
    db_name = kiwoom_cfg["stock_conn"]["stock_db"]
    user_name = kiwoom_cfg["stock_conn"]["stock_user"]
    user_pswd = kiwoom_cfg["stock_conn"]["stock_pswd"]
    # 컬럼 목록 리스트
    list_columns = kiwoom_cfg["stock_conn"]["stock_columns"]
    # 조회하는 간격 초
    term_seconds = kiwoom_cfg["term_seconds"]

dict_agreement = {}

now_dt = datetime.date.today()
DT = str(now_dt.year) + str(now_dt.month).zfill(2) + str(now_dt.day).zfill(2)


# 상수
screen_number = "1234"

# Timestamp for loggers
formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                              datefmt='%Y-%m-%d %H:%M:%S')

# 로그 파일 핸들러
now = datetime.datetime.now().isoformat()[:10]
logf = now + ".log"
logf = os.path.join("logs", logf)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
fh_log = FileHandler(os.path.join(BASE_DIR, logf), encoding='utf-8')
fh_log.setLevel(logging.DEBUG)
fh_log.setFormatter(formatter)

# stdout handler
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(formatter)

# 로거 생성 및 핸들러 등록
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(fh_log)
logger.addHandler(stdout_handler)


def insert_data(dict_value):
    if dict_value["시간"] < "090000":
        return False

    conn = pymysql.connect(
        host=host_ip, 
        port=host_port, 
        user=user_name, 
        password=user_pswd, 
        charset='utf8', 
        database=db_name
    )
    
    sql = "insert into TB_STC_PRC ("
    for col in list_columns:
        sql += col + ","
    sql = sql[:len(sql)-1] + ")" + "\n" + "values\n("
    
    for key, value in dict_value.items():        
        sql += "'" + "".join(value.replace("-", "")) + "',"
    
    sql = sql[:len(sql)-1] + ")"
    print(sql)
    
    cursor = conn.cursor() 
    cursor.execute(sql)        

    conn.commit()
    conn.close()

    return True



class SyncRequestDecorator:
    """키움 API 비동기 함수 데코레이터
    """

    @staticmethod
    def kiwoom_sync_request(func):
        def func_wrapper(self, *args, **kwargs):
            if kwargs.get('nPrevNext', 0) == 0:
                logger.debug('초기 요청 준비')
                self.params = {}
                self.result = {}
            # self.request_thread_worker.request_queue.append((func, args, kwargs))
            logger.debug("요청 실행: %s %s %s" % (func.__name__, args, kwargs))
            func(self, *args, **kwargs)
            self.event = QEventLoop()
            self.event.exec_()
            return self.result  # 콜백 결과 반환
        return func_wrapper

    @staticmethod
    def kiwoom_sync_callback(func):
        def func_wrapper(self, *args, **kwargs):
            logger.debug("요청 콜백: %s %s %s" % (func.__name__, args, kwargs))
            func(self, *args, **kwargs)  # 콜백 함수 호출
        return func_wrapper


class Kiwoom(QAxWidget):

    # 초당 5회 제한이므로 최소한 0.2초 대기해야 함
    # (2018년 10월 기준) 1시간에 1000회 제한하므로 3.6초 이상 대기해야 함
    #rate_limit = 4.0
    rate_limit = 0.5 # But I won't be making too many requests so... Uhm... unused.

    def __init__(self):
        """
        메인 객체
        """
        super().__init__()

        # 키움 시그널 연결
        self.setControl("KHOPENAPI.KHOpenAPICtrl.1")
        self.OnEventConnect.connect(self.kiwoom_OnEventConnect)
        self.OnReceiveTrData.connect(self.kiwoom_OnReceiveTrData)

        # 파라미터
        self.params = {}

        # I dunno what these are but this is missing
        self.dict_stock = {}
        self.dict_callback = {}

        # 요청 결과
        self.event = None
        self.result = {}

    # -------------------------------------
    # 로그인 관련함수
    # -------------------------------------
    @SyncRequestDecorator.kiwoom_sync_request
    def kiwoom_CommConnect(self, **kwargs):
        """로그인 요청 (키움증권 로그인창 띄워줌. 자동로그인 설정시 바로 로그인 진행)
        OnEventConnect() 콜백
        :param kwargs:
        :return: 1: 로그인 요청 성공, 0: 로그인 요청 실패
        """
        lRet = self.dynamicCall("CommConnect()")
        return lRet

    def kiwoom_GetConnectState(self, **kwargs):
        """로그인 상태 확인
        OnEventConnect 콜백
        :param kwargs:
        :return: 0: 연결안됨, 1: 연결됨
        """
        lRet = self.dynamicCall("GetConnectState()")
        return lRet


    @SyncRequestDecorator.kiwoom_sync_callback
    def kiwoom_OnEventConnect(self, nErrCode, **kwargs):
        """로그인 결과 수신
        로그인 성공시 [조건목록 요청]GetConditionLoad() 실행
        :param nErrCode: 0: 로그인 성공, 100: 사용자 정보교환 실패, 101: 서버접속 실패, 102: 버전처리 실패
        :param kwargs:
        :return:
        """
        if nErrCode == 0:
            logger.debug("로그인 성공")
        elif nErrCode == 100:
            logger.debug("사용자 정보교환 실패")
        elif nErrCode == 101:
            logger.debug("서버접속 실패")
        elif nErrCode == 102:
            logger.debug("버전처리 실패")
        
        self.result['result'] = nErrCode
        if self.event is not None:
            self.event.exit()

    # -------------------------------------
    # 조회 관련함수
    # -------------------------------------
    def kiwoom_SetInputValue(self, sID, sValue):
        """
        :param sID:
        :param sValue:
        :return:
        """
        res = self.dynamicCall("SetInputValue(QString, QString)", sID, sValue)
        return res

    def kiwoom_CommRqData(self, sRQName, sTrCode, nPrevNext, sScreenNo):
        """
        :param sRQName:
        :param sTrCode:
        :param nPrevNext:
        :param sScreenNo:
        :return:
        """
        res = self.dynamicCall("CommRqData(QString, QString, int, QString)", sRQName, sTrCode, nPrevNext, sScreenNo)
        return res

    def kiwoom_GetRepeatCnt(self, sTRCode, sRQName):
        """
        :param sTRCode:
        :param sRQName:
        :return:
        """
        res = self.dynamicCall("GetRepeatCnt(QString, QString)", sTRCode, sRQName)
        return res

    def kiwoom_GetCommData(self, sTRCode, sRQName, nIndex, sItemName):
        """
        :param sTRCode:
        :param sRQName:
        :param nIndex:
        :param sItemName:
        :return:
        """
        res = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTRCode, sRQName, nIndex, sItemName)
        return res

    @SyncRequestDecorator.kiwoom_sync_request
    def kiwoom_TR_OPT10001(self, strCode, **kwargs):
        """주식기본정보요청
        :param strCode:
        :param kwargs:
        :return:
        """
        res = self.kiwoom_SetInputValue("종목코드", strCode)
        res = self.kiwoom_CommRqData("주식기본정보", "OPT10001", 0, screen_number)
        return res

    @SyncRequestDecorator.kiwoom_sync_request
    def kiwoom_TR_OPT10003(self, strCode, **kwargs):
        """체결정보요청
        :param strCode:
        :param kwargs:
        :return:
        """
        res = self.kiwoom_SetInputValue("종목코드", strCode)
        res = self.kiwoom_CommRqData("체결정보", "OPT10003", 0, screen_number)
        return res

    @SyncRequestDecorator.kiwoom_sync_callback
    def kiwoom_OnReceiveTrData(self, sScrNo, sRQName, sTRCode, sRecordName, sPreNext, nDataLength, sErrorCode, sMessage, sSPlmMsg, **kwargs):

        if sRQName == "주식기본정보":
            cnt = self.kiwoom_GetRepeatCnt(sTRCode, sRQName)
            list_item_name = ["종목명", "현재가", "등락율", "거래량"]
            종목코드 = self.kiwoom_GetCommData(sTRCode, sRQName, 0, "종목코드")
            종목코드 = 종목코드.strip()
            dict_stock = self.dict_stock.get(종목코드, {})
            for item_name in list_item_name:
                item_value = self.kiwoom_GetCommData(sTRCode, sRQName, 0, item_name)
                item_value = item_value.strip()
                dict_stock[item_name] = item_value
            self.dict_stock[종목코드] = dict_stock
            logger.debug("주식기본정보: %s, %s" % (종목코드, dict_stock))
            if "주식기본정보" in self.dict_callback:
                self.dict_callback["주식기본정보"](dict_stock)

        elif sRQName == "체결정보":
            cnt = self.kiwoom_GetRepeatCnt(sTRCode, sRQName)
            list_item_name = ["시간", "현재가", "우선매도호가단위", "우선매수호가단위"]
            종목코드 = self.kiwoom_GetCommData(sTRCode, sRQName, 0, "종목코드")
            종목코드 = 종목코드.strip()
            dict_stock = self.dict_stock.get(종목코드, {})
            dict_stock["종목코드"] = jongmok_code
            dict_stock["일자"] = DT
            for item_name in list_item_name:
                item_value = self.kiwoom_GetCommData(sTRCode, sRQName, 0, item_name)
                item_value = item_value.strip()
                dict_stock[item_name] = item_value
            # 디비로 데이터 저장
            insert_data(dict_stock)
            
            self.dict_stock[종목코드] = dict_stock
            logger.debug("체결정보: %s, %s" % (종목코드, dict_stock))
            if "체결정보" in self.dict_callback:
                self.dict_callback["체결정보"](dict_stock)
        elif sRQName.startswith("RQ_"):
            logger.debug("RQ handler")
            result = self.kiwoom_GetCommData(sTRCode, sRQName, 0, "")
            logger.debug("result: {}".format(result))
        else:
            logger.debug("Unknown sRQName: {}".format(sRQName))

        if self.event is not None:
            self.event.exit()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    hts = Kiwoom()

    # login
    if hts.kiwoom_GetConnectState() == 0:
        logger.debug('로그인 시도')
        res = hts.kiwoom_CommConnect()
        logger.debug('로그인 결과: {}'.format(res))
        if res.get('result') != 0:
            print("Login failed")
            sys.exit()
    
    # 시간 동안 수행
    while True:
        # 처음은 한번 추출
        #hts.kiwoom_TR_OPT10003(jongmok_code)
        now_dtm = datetime.datetime.now()
        run_hms = str(now_dtm.hour).zfill(2) + str(now_dtm.minute).zfill(2) + str(now_dtm.second).zfill(2)
        # 현재 시각이 지정한 종료 시각보다 크면 그냥 종료를 함
        if (run_hms > run_day_end):
            print("지정한 시각이 지났습니다. 종료합니다.")
            break
        # 하루 동안 지정한 시간에 포함되면 수행
        elif (run_hms >= run_day_start):
            now_dtm = datetime.datetime.now()
            run_minsec = str(now_dtm.minute).zfill(2) + str(now_dtm.second).zfill(2)
            # 하루 중 지정한 분 구간에 포함되면 수행
            if (run_minsec >= run_minute_start and run_minsec <= run_minute_end):
                hts.kiwoom_TR_OPT10003(jongmok_code)
        # 지정한 초 대기
        print("waiting...", run_hms)
        time.sleep(term_seconds)
