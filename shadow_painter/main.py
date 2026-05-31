import sys
from PySide6.QtWidgets import QApplication
from shadow_painter.ui import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
