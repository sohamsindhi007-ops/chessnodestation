import sys, os, time, threading, queue, serial, chess, chess.engine
import tkinter as tk
from threading import Lock

# ── Paths ─────────────────────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR   = sys._MEIPASS
    SCRIPT_DIR = os.getcwd()
else:
    BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
    SCRIPT_DIR = BASE_DIR

STOCKFISH_PATH = os.path.join(BASE_DIR, 'stockfish-windows-x86-64-avx2.exe')
BAUD = 115200 # Increased for faster LED syncing
PIN_RED=2; PIN_YELLOW=3; PIN_GREEN=4; PIN_BLUE=5

# Global board state and Lock for thread safety
current_board = chess.Board()
board_lock = Lock()

# ── Logging ───────────────────────────────────────────────────────────────────
LOG = None
def log(m):
    global LOG
    timestamp = time.strftime('%H:%M:%S')
    msg = f"[{timestamp}] {m}"
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()
    if LOG:
        try: LOG.write(msg + "\n"); LOG.flush()
        except: pass

def init_logging():
    global LOG
    try:
        LOG = open(os.path.join(SCRIPT_DIR, 'engine_log.txt'), 'w', buffering=1)
        return True
    except: return False

init_logging()

# ── Serial Worker ─────────────────────────────────────────────────────────────
serial_queue = queue.Queue()
ser = None

def serial_worker():
    while True:
        cmd = serial_queue.get()
        if cmd is None: break
        if ser and ser.is_open:
            try:
                ser.write((cmd + '\n').encode())
                time.sleep(0.01) # Faster throughput
            except Exception as e:
                log(f"Serial Error: {e}")
        serial_queue.task_done()

def init_arduino():
    global ser
    # Check common ports for Arduino
    for p in [f'COM{i}' for i in range(20, 1, -1)]:
        try:
            ser = serial.Serial(p, BAUD, timeout=1)
            time.sleep(2)
            log(f"✅ Arduino connected on {p}!")
            return True
        except: continue
    log("❌ No Arduino found.")
    return False

arduino_connected = init_arduino()
threading.Thread(target=serial_worker, daemon=True).start()

def send(cmd):
    if arduino_connected: serial_queue.put(cmd)

def lcd(l1, l2=''):
    send(f"LCD:{str(l1).ljust(16)[:16]}|{str(l2).ljust(16)[:16]}")

# ── Stockfish ─────────────────────────────────────────────────────────────────
sf = None
def init_stockfish():
    global sf
    if os.path.exists(STOCKFISH_PATH):
        try:
            sf = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
            return True
        except Exception as e:
            log(f"Stockfish Init Error: {e}")
    return False

# ── Analysis Engine ───────────────────────────────────────────────────────────
def analysis_thread_loop():
    global current_board
    log("🚀 NodeStation Analysis Active")
    lcd("NodeStation", "Waiting...")
    
    while sf:
        try:
            # Thread-safe copy of the board for analysis
            with board_lock:
                analysis_copy = current_board.copy()
            
            info = sf.analyse(analysis_copy, chess.engine.Limit(time=0.1))
            nodes = info.get("nodes", 0)
            depth = info.get("depth", 0)
            
            score_obj = info.get("score").white()
            if score_obj.is_mate():
                score = 10.0 if score_obj.mate() > 0 else -10.0
            else:
                score = (score_obj.score() or 0) / 100.0

            # 1. FIX: Eval Bar Logic (Normalized 0-100)
            # Clamp eval between -5.0 and +5.0 for a readable bar
            clamped_score = max(-5.0, min(5.0, score))
            bar_percent = int(((clamped_score + 5) / 10) * 100)
            send(f"BAR:{bar_percent}")

            # Update LCD
            n_fmt = f"{nodes//1000}k" if nodes > 1000 else str(nodes)
            lcd(f"N:{n_fmt} D:{depth}", f"Eval: {score:+.2f}")

            # 2. FIX: LED Sync Logic (State-based)
            if score > 0.75: # White winning
                send(f"LED_ON:{PIN_GREEN}"); send(f"LED_OFF:{PIN_RED}")
            elif score < -0.75: # Black winning
                send(f"LED_ON:{PIN_RED}"); send(f"LED_OFF:{PIN_GREEN}")
            else: # Equal position
                send(f"LED_OFF:{PIN_GREEN}"); send(f"LED_OFF:{PIN_RED}")
            
            time.sleep(0.1) # Reduced latency
            
        except Exception as e:
            log(f"Analysis Loop Error: {e}")
            time.sleep(1)

# ── GUI ───────────────────────────────────────────────────────────────────────
def start_app():
    root = tk.Tk()
    root.title("NodeStation Pro")
    root.geometry("300x150")
    root.attributes("-topmost", True)
    
    status_text = "NodeStation: ONLINE" if arduino_connected else "NodeStation: NO HW"
    status_label = tk.Label(root, text=status_text, 
                            fg="green" if arduino_connected else "red", font=("Arial", 12))
    status_label.pack(pady=20)
    
    if init_stockfish():
        threading.Thread(target=analysis_thread_loop, daemon=True).start()
    else:
        status_label.config(text="Stockfish Error!", fg="red")

    root.mainloop()

# ── Main UCI Bridge ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    gui_thread = threading.Thread(target=start_app, daemon=True)
    gui_thread.start()

    while True:
        try:
            line = sys.stdin.readline()
            if not line: break
            cmd = line.strip()
            
            # 3. FIX: Position Update Logic with Lock
            if cmd.startswith("position"):
                with board_lock:
                    if "moves" in cmd:
                        moves = cmd.split("moves ")[1].split()
                        current_board = chess.Board()
                        for move in moves:
                            current_board.push_uci(move)
                    elif "startpos" in cmd:
                        current_board = chess.Board()

            elif cmd == "uci":
                print("id name NodeStation_Pro\nid author Hackathon_Team\nuciok")
                sys.stdout.flush()

            elif cmd == "isready":
                print("readyok")
                sys.stdout.flush()

            elif cmd.startswith("go"):
                if sf:
                    result = sf.play(current_board, chess.engine.Limit(time=0.5))
                    print(f"bestmove {result.move}")
                    sys.stdout.flush()

            elif cmd == "quit":
                if sf: sf.quit()
                break

        except Exception as e:
            log(f"UCI Bridge Error: {e}")

