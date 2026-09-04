import sys
import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from src.database.db_manager import DatabaseManager
from src.ui.main_window import MainWindow

def main():
    # Enable High DPI scaling for crisp PDF text and UI icons
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("ReadEra Desktop Reader")
    app.setOrganizationName("ReadEra")

    if os.path.exists("logo.png"):
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon("logo.png"))

    db_manager = DatabaseManager()
    main_window = MainWindow(db_manager)
    main_window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
