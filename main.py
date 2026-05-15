import sys
from PyQt6.QtWidgets import QApplication

import database
from main_window import MainWindow

if __name__ == "__main__":
    database.init_database()
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())