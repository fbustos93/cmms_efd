import eel
import CDIAT_UI
import socket

hostname = socket.gethostname()
serverip = socket.gethostbyname(hostname)
eel.init("U_I/web_inter")

@eel.expose
def run_ui():
    CDIAT_UI.main()

if __name__ == "__main__":
    print(f"server ip: {serverip}")
    eel.start("index.html", size=(900, 600), port=8080, host="0.0.0.0")
