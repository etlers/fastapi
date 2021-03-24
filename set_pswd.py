"""
    비밀번호 등록 화면으로 실계좌 연결에 사용
"""

import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QAxContainer import *


class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python 로그인")
        self.ocx = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.ocx.OnEventConnect.connect(self._handler_login)

        # login
        self.ocx.dynamicCall("CommConnect()")
        self.login_loop = QEventLoop()
        self.login_loop.exec()

        self.ocx.dynamicCall("KOA_Functions(QString, QString)", "ShowAccountWindow", "")

    def _handler_login(self):
        try:
            self.login_loop.exit()
        except:
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MyWindow()
    win.show()
    #app.exec_()